import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  base: process.env.VITE_DEMO_MODE === 'true' ? '/NACC_RACCO1_SYS/' : '/',
  plugins: [react()],
})
