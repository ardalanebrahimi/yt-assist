import { useState, useEffect } from "react"
import Library from "./pages/Library"
import BatchOperations from "./pages/BatchOperations"

type Page = "library" | "batch"

function App() {
  const [page, setPage] = useState<Page>("library")

  // Simple hash-based routing
  useEffect(() => {
    const handleHashChange = () => {
      const hash = window.location.hash.slice(1)
      if (hash === "batch") {
        setPage("batch")
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

  return <Library />
}

export default App
