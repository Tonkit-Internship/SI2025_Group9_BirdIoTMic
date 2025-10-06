FROM public.ecr.aws/lambda/python:3.11 

COPY . /var/task 

RUN pip3 install --no-cache-dir -r requirements.txt 

CMD ["handler.lambda_handler"]