FROM node:20-alpine AS build

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

ARG REACT_APP_API_BASE_URL=/api/
ARG REACT_APP_DEBUG_API=false
ENV REACT_APP_API_BASE_URL=$REACT_APP_API_BASE_URL \
    REACT_APP_DEBUG_API=$REACT_APP_DEBUG_API

RUN npm run build

FROM nginx:1.27-alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/build /usr/share/nginx/html

EXPOSE 3000

CMD ["nginx", "-g", "daemon off;"]
