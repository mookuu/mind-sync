FROM node:20-alpine AS vendor
WORKDIR /build
COPY package.json md-bundle-entry.js ./
RUN npm install --no-audit --no-fund \
  && mkdir -p vendor \
  && npm run build:vendor \
  && cp node_modules/highlight.js/styles/github-dark.min.css vendor/github-dark.min.css

FROM nginx:1.27-alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY index.html /usr/share/nginx/html/index.html
COPY app.js /usr/share/nginx/html/app.js
COPY preview.js /usr/share/nginx/html/preview.js
COPY ui.js /usr/share/nginx/html/ui.js
COPY styles.css /usr/share/nginx/html/styles.css
COPY --from=vendor /build/vendor /usr/share/nginx/html/vendor
