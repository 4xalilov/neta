import { createReadStream } from "node:fs";
import { stat } from "node:fs/promises";
import { PutObjectCommand, S3Client } from "@aws-sdk/client-s3";

export interface S3Config {
  endpoint?: string;
  accessKeyId: string;
  secretAccessKey: string;
  bucket: string;
  region: string;
}

export function s3ConfigFromEnv(env: NodeJS.ProcessEnv = process.env): S3Config {
  const bucket = env.S3_BUCKET;
  if (!bucket) throw new Error("S3_BUCKET is not set");
  return {
    endpoint: env.S3_ENDPOINT || undefined,
    accessKeyId: env.S3_ACCESS_KEY ?? "",
    secretAccessKey: env.S3_SECRET_KEY ?? "",
    bucket,
    region: env.S3_REGION || "us-east-1",
  };
}

let client: S3Client | null = null;

export function getS3Client(cfg: S3Config): S3Client {
  if (!client) {
    client = new S3Client({
      endpoint: cfg.endpoint,
      region: cfg.region,
      forcePathStyle: true, // MinIO
      credentials: { accessKeyId: cfg.accessKeyId, secretAccessKey: cfg.secretAccessKey },
    });
  }
  return client;
}

/** Upload a local file to s3://bucket/key; returns the uploaded size in bytes. */
export async function uploadFile(
  localPath: string,
  key: string,
  cfg: S3Config = s3ConfigFromEnv(),
  contentType = "video/mp4",
): Promise<{ uri: string; sizeBytes: number }> {
  const { size } = await stat(localPath);
  await getS3Client(cfg).send(
    new PutObjectCommand({
      Bucket: cfg.bucket,
      Key: key,
      Body: createReadStream(localPath),
      ContentLength: size,
      ContentType: contentType,
    }),
  );
  return { uri: `s3://${cfg.bucket}/${key}`, sizeBytes: size };
}
