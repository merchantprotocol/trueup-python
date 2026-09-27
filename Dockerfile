# Test image: installs the SDK and runs its tests (live tests need TRUEUP_API_KEY).
FROM python:3.12-slim
WORKDIR /sdk
COPY . .
RUN pip install --no-cache-dir -e ".[test]"
CMD ["pytest", "-v"]
