# GridWise Submission Information

Copy this file to `SUBMISSION_INFO.md` only when the external resources are ready. Replace every placeholder and re-run `python scripts/check_release.py` before submission. Never place an API key or access token here.

## Required links

- Public API base URL: `<https://your-service.example.com>`
- Health endpoint: `<https://your-service.example.com/health>`
- Optimization endpoint: `<https://your-service.example.com/optimize-energy>`
- GitHub repository: `<https://github.com/owner/repository>`
- Pullable Docker image with immutable digest: `<registry/image@sha256:digest>`
- Three-minute video: `<https://video-host.example.com/...>`

## Final external verification

- [ ] `GET /health` returns HTTP 200 and exactly `{"status":"ok"}`.
- [ ] `POST /optimize-energy` accepts `samples/sample_request.json` without authentication.
- [ ] The response completes within 30 seconds and contains 24 plan rows.
- [ ] The repository visibility follows the event timing rules.
- [ ] The Docker image pulls and starts on port 8000 with environment-provided credentials.
- [ ] The video is accessible and no longer than three minutes.
- [ ] All links remain available throughout evaluation.

## Safe deployment variables

Configure these in the hosting platform, not in the repository:

```text
LLM_API_KEY=<secret>
LLM_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
LLM_MODEL=gemini-2.5-flash
LLM_TIMEOUT_S=10
LLM_MAX_RETRIES=2
LLM_STUB=0
LOG_LEVEL=INFO
```
