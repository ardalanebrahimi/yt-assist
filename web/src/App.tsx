import { useState, useEffect } from "react"
import Library from "./pages/Library"
import BatchOperations from "./pages/BatchOperations"
import QA from "./pages/QA"
import ContentStudio from "./pages/ContentStudio"

type Page = "library" | "batch" | "qa" | "studio"

function App() {
  const [page, setPage] = useState<Page>("library")

  // Simple hash-based routing
  useEffect(() => {
    const handleHashChange = () => {
      const hash = window.location.hash.slice(1)
      if (hash === "batch") {
        setPage("batch")
      } else if (hash === "qa") {
        setPage("qa")
      } else if (hash === "studio") {
        setPage("studio")
      } else {
        setPage("library")
      }
    }

    handleHashChange()
    window.addEventListener("hashchange", handleHashChange)
    return () => window.removeEventListener("hashchange", handleHashChange)
  }, [])

  // Expose navigation function globally for components
  useEffect(() => {
    (window as any).navigateTo = (p: Page) => {
      window.location.hash = p === "library" ? "" : p
    }
  }, [])

  if (page === "batch") {
    return <BatchOperations />
  }

  if (page === "qa") {
    return <QA />
  }

  if (page === "studio") {
    return <ContentStudio />
  }

  return <Library />
}

export default App
