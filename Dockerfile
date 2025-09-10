# Use the official AWS Lambda Python runtime
FROM public.ecr.aws/lambda/python:3.11

# Install system dependencies for audio processing
RUN yum update -y && \
    yum install -y gcc-c++ cmake && \
    yum clean all

# Copy requirements first for better layer caching
COPY requirements-minimal.txt ${LAMBDA_TASK_ROOT}/

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements-minimal.txt

# Copy application code
COPY app/ ${LAMBDA_TASK_ROOT}/app/
COPY alembic/ ${LAMBDA_TASK_ROOT}/alembic/
COPY alembic.ini ${LAMBDA_TASK_ROOT}/

# Set the CMD to your handler
CMD ["app.main.handler"]