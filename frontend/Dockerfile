# AsliNumber frontend image: runs the Vite dev server for local Compose
# use (per docs/aslinumber-implementation-plan.md's local deployment
# section). Not a production build -- a production image would run a
# static file server over `vite build`'s output instead; that's deferred
# to a later phase's deployment work.
FROM node:20-slim

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]