# syntax=docker/dockerfile:1.7

# ----------------------------------------------------------------- deps
FROM node:24-alpine AS deps

WORKDIR /app

# The manifests only: a source change must not invalidate the install layer.
COPY package.json package-lock.json ./
RUN npm ci

# ------------------------------------------------------------------ dev
FROM node:24-alpine AS dev

WORKDIR /app
ENV NODE_ENV=development

COPY --from=deps /app/node_modules ./node_modules
COPY . .

EXPOSE 4200
CMD ["npm", "start"]

# ---------------------------------------------------------------- build
FROM node:24-alpine AS build

WORKDIR /app

COPY --from=deps /app/node_modules ./node_modules
COPY . .

RUN npm run build -- --configuration production

# ----------------------------------------------------------------- prod
# Not a server. The compose prod overlay runs this image once to copy the built
# bundle into a volume that nginx serves.
FROM node:24-alpine AS prod

WORKDIR /app

COPY --from=build /app/dist ./dist

CMD ["sh", "-c", "cp -r /app/dist/frontend/browser/. /dist/"]
