# Use the official AWS Lambda Python runtime
FROM public.ecr.aws/lambda/python:3.11

# Copy requirements first for better layer caching
COPY requirements.txt ${LAMBDA_TASK_ROOT}/

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ ${LAMBDA_TASK_ROOT}/app/
COPY alembic/ ${LAMBDA_TASK_ROOT}/alembic/
COPY alembic.ini ${LAMBDA_TASK_ROOT}/

# Set the CMD to your handler
CMD ["app.main.handler"]