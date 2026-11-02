import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'
import { installNameHighlight } from './utils/nameHighlight'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>,
)

// Thin gold outline wherever "Shams" or "Tahzib" appears on screen.
installNameHighlight()
