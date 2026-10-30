# Web Frontend

React + TypeScript (Vite) web application for the Cloud File Exchange System.

Run `npm install` and `npm run dev` from this directory for local development.
Development uses the in-memory file fixtures in `src/api/client.ts` by default.
Set `VITE_USE_MOCK_DATA=false` to connect to the API at the same origin.

Run `npm run build` to type-check and create the production bundle. The Docker
image builds that bundle with Node and serves it through Nginx on port 5173.
