FROM node:24-alpine

WORKDIR /frontend

COPY package.json package-lock.json ./
RUN npm ci --include=dev

COPY . .

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
