# Owner actions — signal-foundry

Manual steps unavailable via API.

## 1. GitHub repository social preview (manual upload)

Pages `og:image` (`https://ianlyoo.github.io/signal-foundry/assets/social-preview.png`) is automatic. Repository card needs manual upload:

- Path: Settings → General → Social preview → Edit → Upload an image
- File: `docs/assets/social-preview.png` (1280×640, <1 MiB, #0f172a)

Verification:

```bash
gh api graphql -f query='query{repository(owner:"ianlyoo",name:"signal-foundry"){openGraphImageUrl}}'
# before: https://opengraph.githubassets.com/... (default)
# after:  user-images URL
```

Live Pages:

```bash
curl -fsSL https://ianlyoo.github.io/signal-foundry/ | grep -o 'og:image[^>]*content="[^"]*"'
curl -fsSL https://ianlyoo.github.io/signal-foundry/assets/social-preview.png -o /tmp/p.png && ls -lh /tmp/p.png
```

## 2. Optional pin

- Profile → Customize your pins → select `ianlyoo/signal-foundry`

## 3. Do not attempt

- No API upload for social preview.
- No force push.
