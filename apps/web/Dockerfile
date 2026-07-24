FROM node:20-alpine AS base
ENV PNPM_HOME="/pnpm"
ENV PATH="$PNPM_HOME:$PATH"
RUN corepack enable && corepack prepare pnpm@9.15.4 --activate
WORKDIR /app

FROM base AS deps
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY apps/web/package.json ./apps/web/package.json
RUN pnpm install --frozen-lockfile --ignore-scripts

FROM base AS builder
ARG NEXT_PUBLIC_API_BASE_URL
ARG NEXT_PUBLIC_SUPABASE_URL
ARG NEXT_PUBLIC_SUPABASE_ANON_KEY
ARG NEXT_PUBLIC_APP_ENV=production
ARG NEXT_PUBLIC_USE_API=true
ARG NEXT_PUBLIC_SUPABASE_AUTH=true
ARG NEXT_PUBLIC_DEFAULT_WORKSPACE_ID
ARG NEXT_PUBLIC_DEFAULT_PROJECT_ID
ENV NEXT_PUBLIC_API_BASE_URL=$NEXT_PUBLIC_API_BASE_URL \
    NEXT_PUBLIC_SUPABASE_URL=$NEXT_PUBLIC_SUPABASE_URL \
    NEXT_PUBLIC_SUPABASE_ANON_KEY=$NEXT_PUBLIC_SUPABASE_ANON_KEY \
    NEXT_PUBLIC_APP_ENV=$NEXT_PUBLIC_APP_ENV \
    NEXT_PUBLIC_USE_API=$NEXT_PUBLIC_USE_API \
    NEXT_PUBLIC_SUPABASE_AUTH=$NEXT_PUBLIC_SUPABASE_AUTH \
    NEXT_PUBLIC_DEFAULT_WORKSPACE_ID=$NEXT_PUBLIC_DEFAULT_WORKSPACE_ID \
    NEXT_PUBLIC_DEFAULT_PROJECT_ID=$NEXT_PUBLIC_DEFAULT_PROJECT_ID
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN pnpm --filter @nova/web build

FROM node:20-alpine AS runner
ENV NODE_ENV=production
WORKDIR /app
COPY --from=builder /app/package.json ./package.json
COPY --from=builder /app/pnpm-workspace.yaml ./pnpm-workspace.yaml
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/apps/web ./apps/web
EXPOSE 3000
CMD ["pnpm", "--filter", "@nova/web", "start"]
