# ใช้ base image ของ Lambda (Python 3.11)
FROM public.ecr.aws/lambda/python:3.11

# 1️⃣ ติดตั้ง FFmpeg จาก static binary
COPY --from=mwader/static-ffmpeg:latest /ffmpeg /usr/local/bin/
COPY --from=mwader/static-ffmpeg:latest /ffprobe /usr/local/bin/

# 2️⃣ ติดตั้ง compiler + lib ที่จำเป็น
RUN yum install -y gcc gcc-c++ make libsndfile sndfile-devel \
    && yum clean all \
    && rm -rf /var/cache/yum

# 3️⃣ ตั้งค่า Path ให้ soundfile หา libsndfile ได้
ENV LD_LIBRARY_PATH=/usr/lib64:$LD_LIBRARY_PATH

# 4️⃣ คัดลอกโค้ดและโมเดล BirdNET ทั้งหมด
COPY . /var/task/

# 5️⃣ อัปเดต pip/setuptools ก่อนติดตั้ง dependencies
RUN pip install --upgrade pip setuptools wheel

# 6️⃣ ติดตั้ง dependencies ทั้งหมด (เฉพาะ wheel ที่มี binary)
RUN pip install --no-cache-dir -r requirements.txt --only-binary=:all:

# 7️⃣ ตั้ง entrypoint สำหรับ Lambda
CMD ["handler.lambda_handler"]
