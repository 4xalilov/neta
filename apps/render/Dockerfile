# Remotion render worker (roadmap 1.6). Build: docker build -t neta-render apps/render
FROM node:22-bookworm

# Shared libraries chrome-headless-shell needs (https://www.remotion.dev/docs/miscellaneous/linux-dependencies)
# + fonts for emoji / non-Latin fallback. Remotion ships its own ffmpeg/ffprobe
# (@remotion/compositor-*), so the system ffmpeg is optional (debugging only):
#   docker build --build-arg WITH_FFMPEG=1 ...
ARG WITH_FFMPEG=0
# Browser: by default Remotion's chrome-headless-shell is downloaded at build time
# (needs egress to remotion.media). If that host is blocked, build with
#   --build-arg REMOTION_BROWSER=/usr/bin/chromium
# to use Debian's chromium instead (driven in "chrome-for-testing" mode).
ARG REMOTION_BROWSER=
ENV REMOTION_BROWSER=${REMOTION_BROWSER}
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      libnss3 libdbus-1-3 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 libgbm1 libasound2 \
      libxrandr2 libxkbcommon0 libxfixes3 libxcomposite1 libxdamage1 libpango-1.0-0 libcairo2 \
      fonts-noto-color-emoji fonts-noto-core ca-certificates \
 && if [ "$WITH_FFMPEG" = "1" ]; then apt-get install -y --no-install-recommends ffmpeg; fi \
 && if [ "$REMOTION_BROWSER" = "/usr/bin/chromium" ]; then apt-get install -y --no-install-recommends chromium; fi \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
ENV NODE_ENV=production \
    RENDER_QUEUE=render

COPY package.json package-lock.json ./
# devDependencies are not needed at runtime (tsx is a regular dependency).
RUN npm ci --omit=dev
# Download chrome-headless-shell into node_modules/.remotion at build time, so
# the worker never downloads a browser at runtime (skipped with apt chromium).
RUN if [ -z "$REMOTION_BROWSER" ]; then npx remotion browser ensure; fi

COPY . .

# node directly (not npm) so SIGTERM reaches the worker for a graceful close.
CMD ["node", "--import", "tsx", "src/worker.ts"]
