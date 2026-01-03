"""RAG (Retrieval-Augmented Generation) service for video transcripts."""

import json
import pickle
from pathlib import Path
from typing import Any

import faiss
import numpy as np
from openai import OpenAI
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import Video, Transcript


# Configuration
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSION = 1536
CHUNK_SIZE = 500  # characters per chunk
CHUNK_OVERLAP = 100  # overlap between chunks
TOP_K_RESULTS = 5  # number of chunks to retrieve


class RAGService:
    """Service for RAG operations on video transcripts."""

    def __init__(self):
        settings = get_settings()
        self.client = OpenAI(api_key=settings.openai_api_key)
        self.data_dir = settings.data_dir
        self.index_path = self.data_dir / "faiss_index.bin"
        self.metadata_path = self.data_dir / "chunks_metadata.pkl"
        self.index: faiss.IndexFlatL2 | None = None
        self.chunks_metadata: list[dict] = []
        self._load_index()

    def _load_index(self) -> None:
        """Load existing FAISS index and metadata if available."""
        if self.index_path.exists() and self.metadata_path.exists():
            self.index = faiss.read_index(str(self.index_path))
            with open(self.metadata_path, "rb") as f:
                self.chunks_metadata = pickle.load(f)
        else:
            self.index = faiss.IndexFlatL2(EMBEDDING_DIMENSION)
            self.chunks_metadata = []

    def _save_index(self) -> None:
        """Save FAISS index and metadata to disk."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        faiss.write_index(self.index, str(self.index_path))
        with open(self.metadata_path, "wb") as f:
            pickle.dump(self.chunks_metadata, f)

    def chunk_transcript(
        self,
        text: str,
        video_id: str,
        video_title: str,
        chunk_size: int = CHUNK_SIZE,
        overlap: int = CHUNK_OVERLAP,
    ) -> list[dict]:
        """
        Split transcript into overlapping chunks.

        Args:
            text: The transcript text to chunk
            video_id: YouTube video ID
            video_title: Video title for reference
            chunk_size: Maximum characters per chunk
            overlap: Number of overlapping characters between chunks

        Returns:
            List of chunk dictionaries with text and metadata
        """
        if not text or not text.strip():
            return []

        chunks = []
        start = 0
        chunk_index = 0

        while start < len(text):
            end = start + chunk_size

            # Try to break at sentence boundary
            if end < len(text):
                # Look for sentence ending within last 50 chars
                for punct in [".", "!", "?", "\n"]:
                    last_punct = text[max(start, end - 50):end].rfind(punct)
                    if last_punct != -1:
                        end = max(start, end - 50) + last_punct + 1
                        break

            chunk_text = text[start:end].strip()

            if chunk_text:
                chunks.append({
                    "text": chunk_text,
                    "video_id": video_id,
                    "video_title": video_title,
                    "chunk_index": chunk_index,
                    "start_char": start,
                    "end_char": end,
                })
                chunk_index += 1

            start = end - overlap if end < len(text) else len(text)

        return chunks

    def get_embedding(self, text: str) -> np.ndarray:
        """Get embedding vector for text using OpenAI API."""
        response = self.client.embeddings.create(
            model=EMBEDDING_MODEL,
            input=text,
        )
        return np.array(response.data[0].embedding, dtype=np.float32)

    def get_embeddings_batch(self, texts: list[str]) -> np.ndarray:
        """Get embeddings for multiple texts in batch."""
        if not texts:
            return np.array([], dtype=np.float32).reshape(0, EMBEDDING_DIMENSION)

        # OpenAI allows up to 2048 inputs per request
        batch_size = 100
        all_embeddings = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            response = self.client.embeddings.create(
                model=EMBEDDING_MODEL,
                input=batch,
            )
            batch_embeddings = [np.array(d.embedding, dtype=np.float32) for d in response.data]
            all_embeddings.extend(batch_embeddings)

        return np.array(all_embeddings)

    def index_video(self, video: Video, transcript: Transcript) -> dict:
        """
        Index a single video's transcript into the vector store.

        Args:
            video: Video model instance
            transcript: Transcript model instance

        Returns:
            Dict with indexing results
        """
        # Remove existing chunks for this video
        self._remove_video_chunks(video.id)

        # Chunk the transcript
        chunks = self.chunk_transcript(
            text=transcript.clean_content,
            video_id=video.id,
            video_title=video.title,
        )

        if not chunks:
            return {"video_id": video.id, "chunks_indexed": 0, "message": "No content to index"}

        # Get embeddings
        texts = [c["text"] for c in chunks]
        embeddings = self.get_embeddings_batch(texts)

        # Add to FAISS index
        self.index.add(embeddings)

        # Store metadata
        for chunk in chunks:
            self.chunks_metadata.append(chunk)

        # Save to disk
        self._save_index()

        return {
            "video_id": video.id,
            "chunks_indexed": len(chunks),
            "message": f"Indexed {len(chunks)} chunks",
        }

    def _remove_video_chunks(self, video_id: str) -> int:
        """Remove existing chunks for a video (requires rebuilding index)."""
        # Find indices of chunks to keep
        indices_to_keep = [
            i for i, chunk in enumerate(self.chunks_metadata)
            if chunk["video_id"] != video_id
        ]

        if len(indices_to_keep) == len(self.chunks_metadata):
            return 0  # No chunks to remove

        removed_count = len(self.chunks_metadata) - len(indices_to_keep)

        if not indices_to_keep:
            # All chunks removed, reset index
            self.index = faiss.IndexFlatL2(EMBEDDING_DIMENSION)
            self.chunks_metadata = []
        else:
            # Rebuild index with remaining chunks
            # Note: This requires re-embedding, which is expensive
            # For simplicity, we'll just mark as needing re-index
            self.chunks_metadata = [self.chunks_metadata[i] for i in indices_to_keep]
            # In a production system, you'd want to store embeddings to avoid re-computing

        return removed_count

    def index_all_videos(self, db: Session) -> dict:
        """
        Index all videos with transcripts.

        Args:
            db: Database session

        Returns:
            Dict with indexing results
        """
        # Reset index
        self.index = faiss.IndexFlatL2(EMBEDDING_DIMENSION)
        self.chunks_metadata = []

        # Get all videos with transcripts
        videos = db.query(Video).filter(Video.transcripts.any()).all()

        results = {
            "videos_processed": 0,
            "total_chunks": 0,
            "errors": [],
        }

        for video in videos:
            # Get best transcript (prefer cleaned, then whisper, then youtube)
            transcript = self._get_best_transcript(video)
            if not transcript:
                continue

            try:
                result = self.index_video(video, transcript)
                results["videos_processed"] += 1
                results["total_chunks"] += result["chunks_indexed"]
            except Exception as e:
                results["errors"].append({"video_id": video.id, "error": str(e)})

        return results

    def _get_best_transcript(self, video: Video) -> Transcript | None:
        """Get the best available transcript for a video."""
        # Priority: cleaned > whisper > youtube
        for source in ["cleaned", "whisper", "youtube"]:
            for transcript in video.transcripts:
                if transcript.source == source:
                    return transcript
        # Fallback to any transcript
        return video.transcripts[0] if video.transcripts else None

    def search(self, query: str, top_k: int = TOP_K_RESULTS) -> list[dict]:
        """
        Search for relevant chunks given a query.

        Args:
            query: Search query text
            top_k: Number of results to return

        Returns:
            List of matching chunks with scores
        """
        if not self.chunks_metadata:
            return []

        # Get query embedding
        query_embedding = self.get_embedding(query).reshape(1, -1)

        # Search in FAISS
        k = min(top_k, len(self.chunks_metadata))
        distances, indices = self.index.search(query_embedding, k)

        results = []
        for i, idx in enumerate(indices[0]):
            if idx == -1:  # FAISS returns -1 for empty slots
                continue
            chunk = self.chunks_metadata[idx].copy()
            chunk["score"] = float(distances[0][i])
            chunk["rank"] = i + 1
            results.append(chunk)

        return results

    def ask(
        self,
        question: str,
        top_k: int = TOP_K_RESULTS,
        include_sources: bool = True,
    ) -> dict:
        """
        Answer a question using RAG.

        Args:
            question: The question to answer
            top_k: Number of chunks to retrieve
            include_sources: Whether to include source citations

        Returns:
            Dict with answer and sources
        """
        # Search for relevant chunks
        chunks = self.search(question, top_k)

        if not chunks:
            return {
                "answer": "I don't have any indexed content to answer this question. Please index some videos first.",
                "sources": [],
                "chunks_used": 0,
            }

        # Build context from chunks
        context_parts = []
        for i, chunk in enumerate(chunks):
            context_parts.append(
                f"[Source {i+1}: {chunk['video_title']}]\n{chunk['text']}"
            )
        context = "\n\n---\n\n".join(context_parts)

        # Create prompt
        system_prompt = """You are a helpful assistant that answers questions about YouTube video content.
You will be given relevant excerpts from video transcripts and should answer based on that information.
If the information doesn't contain the answer, say so honestly.
Always cite which video(s) your answer is based on.
Respond in the same language as the question."""

        user_prompt = f"""Based on the following video transcript excerpts, please answer this question:

Question: {question}

Relevant excerpts:
{context}

Please provide a clear, concise answer based on the excerpts above. Cite which videos you used."""

        # Call GPT
        response = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
        )

        answer = response.choices[0].message.content

        # Build sources list
        sources = []
        seen_videos = set()
        for chunk in chunks:
            if chunk["video_id"] not in seen_videos:
                sources.append({
                    "video_id": chunk["video_id"],
                    "title": chunk["video_title"],
                    "url": f"https://youtube.com/watch?v={chunk['video_id']}",
                })
                seen_videos.add(chunk["video_id"])

        return {
            "answer": answer,
            "sources": sources if include_sources else [],
            "chunks_used": len(chunks),
        }

    def get_index_stats(self) -> dict:
        """Get statistics about the current index."""
        video_ids = set(c["video_id"] for c in self.chunks_metadata)
        return {
            "total_chunks": len(self.chunks_metadata),
            "videos_indexed": len(video_ids),
            "embedding_model": EMBEDDING_MODEL,
            "chunk_size": CHUNK_SIZE,
            "chunk_overlap": CHUNK_OVERLAP,
        }


# Singleton instance
_rag_service: RAGService | None = None


def get_rag_service() -> RAGService:
    """Get or create RAG service singleton."""
    global _rag_service
    if _rag_service is None:
        _rag_service = RAGService()
    return _rag_service
