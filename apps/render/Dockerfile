FROM node:20-bookworm
RUN apt-get update && apt-get install -y ffmpeg libnss3 libatk-bridge2.0-0 libgbm1 libasound2 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY package.json .
RUN npm install
COPY . .
CMD ["node", "src/worker.js"]
