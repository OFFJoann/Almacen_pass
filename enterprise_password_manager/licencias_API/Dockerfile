FROM public.ecr.aws/lambda/python:3.12


COPY requirements.txt .

COPY licenses.json .


RUN pip install -r requirements.txt


COPY . .


CMD ["main.lambda_handler"]
