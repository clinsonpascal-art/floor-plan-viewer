import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import ContinuumUnitPOC from './ContinuumUnitPOC.jsx'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <ContinuumUnitPOC />
  </StrictMode>,
)
