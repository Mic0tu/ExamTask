#!/bin/sh
set -e

until mc alias set myminio "http://${MINIO_HOST}:${MINIO_PORT}" "${S3_USER}" "${S3_PASS}"; do
  echo "Waiting for MinIO..."
  sleep 2
done

mc mb "myminio/upload" --ignore-existing
mc mb "myminio/original" --ignore-existing
mc mb "myminio/large" --ignore-existing
mc mb "myminio/medium" --ignore-existing
mc mb "myminio/small" --ignore-existing

mc anonymous set download "myminio/original"
mc anonymous set download "myminio/large"
mc anonymous set download "myminio/medium"
mc anonymous set download "myminio/small"

i=0
while [ "$i" -lt 30 ]; do
  if mc event add "myminio/upload" "arn:minio:sqs::img:webhook" --event put 2>/dev/null; then
    echo "Webhook event configured"
    break
  fi
  if mc event list "myminio/upload" 2>/dev/null | grep -q "img:webhook"; then
    echo "Webhook event already configured"
    break
  fi
  i=$((i + 1))
  echo "Waiting for webhook target..."
  sleep 2
done

if [ "$i" -eq 30 ]; then
  echo "Failed to configure webhook event"
  exit 1
fi

echo "MinIO initialized"
