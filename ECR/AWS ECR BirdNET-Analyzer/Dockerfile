FROM public.ecr.aws/lambda/python:3.11

# 1. ติดตั้ง FFmpeg
COPY --from=mwader/static-ffmpeg:latest /ffmpeg /usr/local/bin/

# 2. ติดตั้ง Library ระบบ
RUN yum install -y gcc gcc-c++ pkgconfig libsndfile sndfile-devel

# 3. ตั้งค่า Path
ENV LD_LIBRARY_PATH=/usr/lib64:$LD_LIBRARY_PATH

# 4. ก๊อปปี้ไฟล์ทั้งหมด (รวม BirdNET_GLOBAL_6K_V2.4_Model และ birdnet_analyzer)
COPY . /var/task/

# 5. ติดตั้ง Python Libraries
RUN pip install --no-cache-dir -r requirements.txt --only-binary=:all:

CMD ["handler.lambda_handler"]