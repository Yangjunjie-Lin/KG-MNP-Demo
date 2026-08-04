FROM node:20-alpine AS build

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY index.html postcss.config.mjs tsconfig.json vite.config.ts ./
COPY scripts ./scripts
COPY src ./src

RUN test -f src/api/generated/schema.ts

ARG VITE_API_BASE_URL=/api/v1
ARG VITE_DATA_SOURCE=api
ARG VITE_ENABLE_TECHNICAL_VIEW=false
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}
ENV VITE_DATA_SOURCE=${VITE_DATA_SOURCE}
ENV VITE_ENABLE_TECHNICAL_VIEW=${VITE_ENABLE_TECHNICAL_VIEW}

RUN npm run build

FROM nginx:1.27-alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
