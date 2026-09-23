import { writeFile } from "node:fs/promises";
import { beforeEach, describe, expect, it, vi } from "vitest";

const renderMedia = vi.fn(async (opts: { outputLocation: string }) => {
  await writeFile(opts.outputLocation, Buffer.alloc(4321, 1));
  return { buffer: null, slowestFrames: [] };
});
const selectComposition = vi.fn(async () => ({
  id: "ReelsBasic",
  width: 1080,
  height: 1920,
  fps: 30,
  durationInFrames: 390,
}));
vi.mock("@remotion/renderer", () => ({ renderMedia, selectComposition }));

const bundle = vi.fn(async () => "/tmp/fake-bundle");
vi.mock("@remotion/bundler", () => ({ bundle }));

const send = vi.fn(async () => ({}));
vi.mock("@aws-sdk/client-s3", () => ({
  S3Client: vi.fn(function (this: { send: typeof send }) {
    this.send = send;
  }),
  PutObjectCommand: vi.fn(function (this: { input: unknown }, input: unknown) {
    this.input = input;
  }),
}));

process.env.S3_BUCKET = "assets";
process.env.S3_ENDPOINT = "http://minio:9000";
process.env.S3_ACCESS_KEY = "k";
process.env.S3_SECRET_KEY = "s";
process.env.REMOTION_BROWSER = "/opt/chrome";
delete process.env.REMOTION_SERVE_URL;

const { processRenderJob } = await import("../job");
const { processor } = await import("../worker");
const { UnrecoverableError } = await import("bullmq");

const jobData = {
  jobId: "job-1",
  workspaceId: "ws-1",
  composition: "ReelsBasic",
  props: { scenes: [{ imageUrl: "https://x/a.png", durationS: 13 }] },
  outputKey: "renders/ws-1/job-1.mp4",
};

describe("render worker", () => {
  beforeEach(() => {
    renderMedia.mockClear();
    selectComposition.mockClear();
    send.mockClear();
  });

  it("renders, uploads and returns the result shape", async () => {
    const res = await processRenderJob(jobData);
    expect(bundle).toHaveBeenCalledTimes(1);
    expect(res).toEqual({
      videoUri: "s3://assets/renders/ws-1/job-1.mp4",
      durationS: 13,
      sizeBytes: 4321,
      renderMs: expect.any(Number),
    });

    const renderArgs = renderMedia.mock.calls[0]![0] as unknown as Record<string, unknown>;
    expect(renderArgs).toMatchObject({
      codec: "h264",
      serveUrl: "/tmp/fake-bundle",
      browserExecutable: "/opt/chrome",
      chromeMode: "chrome-for-testing",
    });
    // Props reach Remotion with schema defaults applied.
    expect((renderArgs.inputProps as { brand: { accent: string } }).brand.accent).toBe("#FACC15");
    expect(selectComposition).toHaveBeenCalledWith(expect.objectContaining({ id: "ReelsBasic" }));

    const put = (send.mock.calls[0] as unknown as [{ input: Record<string, unknown> }])[0].input;
    expect(put).toMatchObject({
      Bucket: "assets",
      Key: "renders/ws-1/job-1.mp4",
      ContentType: "video/mp4",
      ContentLength: 4321,
    });
  });

  it("bundles only once per process", async () => {
    // The first test already bundled; further jobs reuse the cached serve URL.
    const before = bundle.mock.calls.length;
    await processRenderJob({ ...jobData, jobId: "job-2" });
    await processRenderJob({ ...jobData, jobId: "job-3" });
    expect(bundle.mock.calls.length).toBe(before);
    expect(renderMedia).toHaveBeenCalledTimes(2);
  });

  it("throws (→ BullMQ retry) when rendering fails", async () => {
    renderMedia.mockRejectedValueOnce(new Error("chrome crashed"));
    await expect(processRenderJob(jobData)).rejects.toThrow("chrome crashed");
    expect(send).not.toHaveBeenCalled();
  });

  it("processor marks invalid payloads unrecoverable (no retry)", async () => {
    const job = { id: "bad", data: { jobId: "bad" }, attemptsMade: 0, updateProgress: vi.fn() };
    await expect(processor(job as never)).rejects.toBeInstanceOf(UnrecoverableError);
    expect(renderMedia).not.toHaveBeenCalled();
  });

  it("processor returns the job result", async () => {
    const job = { id: "ok", data: jobData, attemptsMade: 0, updateProgress: vi.fn(async () => undefined) };
    const res = await processor(job as never);
    expect(res.videoUri).toBe("s3://assets/renders/ws-1/job-1.mp4");
  });
});
