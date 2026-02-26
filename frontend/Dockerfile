FROM node:20-alpine AS builder

WORKDIR /app

# Install dependencies based on the preferred package manager
COPY package.json package-lock.json* ./
RUN npm ci

# Copy application code
COPY . .

# Build NEXT.js application
RUN npm run build

# Production image
FROM node:20-alpine AS runner

WORKDIR /app

ENV NODE_ENV=production
# Uncomment the following line to disable telemetry at run time
# ENV NEXT_TELEMETRY_DISABLED=1

# Copy only the necessary files for the frontend application
COPY --from=builder /app/package.json ./
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/public ./public

EXPOSE 3000

ENV PORT=3000

CMD ["npm", "start"]
