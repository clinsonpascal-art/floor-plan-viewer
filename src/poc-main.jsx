import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import PrimaryRoomPOC from './PrimaryRoomPOC.jsx'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <PrimaryRoomPOC />
  </StrictMode>,
)
