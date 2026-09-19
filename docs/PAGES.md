# Static website deployment

The Pages website checks a visitor's local ClipNest component and distributes
installation packages. It does not run Python, parse platform links or relay
media. The full downloader opens on the visitor's own loopback address.

## Local build

```sh
python scripts/build_local_site.py --output dist/pages-review
```

Deploy only `dist/pages-review/site/`. The builder uses Python's standard library,
does not install dependencies, and refuses to overwrite an existing directory.
Generated packages are artifacts; do not add them to the source tree.

## GitHub Pages

After the project owner approves public publication:

1. Upload the reviewed source, including `.github/workflows/pages.yml`.
2. In repository **Settings → Pages**, choose **GitHub Actions** as the source.
3. Manually run **Publish ClipNest website** from the reviewed `main` branch.
4. Verify the deployment result, HTTPS website, package downloads and hashes.
5. Test environment discovery in a normal browser with the local component
   running; a browser permission prompt must be handled by the user.

The intended project URL is `https://xialuyu5-oss.github.io/clipnest/`.
There is no automatic trigger on push, pull requests or a schedule. No paid
service, custom domain, account secret or long-lived token is required by this
workflow. Its build job reads source; its deploy job can publish Pages through
GitHub's short-lived deployment identity. Do not upload `.env`, task data or logs.

The local component allows the origin `https://xialuyu5-oss.github.io` by default.
For another host, set its exact HTTPS origin as `LOCAL_SITE_ORIGIN` in the local
configuration. Permission denial remains a connection failure, not evidence of
missing dependencies. Public deployment cannot make an absent/stopped local
component run automatically.

Workflow structure follows [GitHub's custom Pages workflow documentation](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages).
