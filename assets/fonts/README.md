# Bundled font sources

These font files are self-hosted. Visitors make no requests to a third-party font provider.

- Inter: `google/fonts`, `ofl/inter/Inter[opsz,wght].ttf`, converted losslessly to WOFF.
- Source Sans 3: `google/fonts`, `ofl/sourcesans3/SourceSans3[wght].ttf`, converted losslessly to WOFF.
- IBM Plex Sans: `google/fonts`, `ofl/ibmplexsans/IBMPlexSans[wdth,wght].ttf`, converted losslessly to WOFF.
- Source Serif 4: `adobe-fonts/source-serif`, `WOFF2/VAR/SourceSerif4Variable-Roman.ttf.woff2`, retained as supplied.

Retrieved October 9, 2026. No glyphs were removed. Original names and copyright metadata are preserved. The corresponding SIL Open Font License texts are included in this directory.

Google Sans: Fontsource `@fontsource/google-sans` 5.3.2 (npm), files `google-sans-latin-400-normal.woff2` (SHA-256 `2634df0d79333ea639d7079f566163bb700a57783d3a8f09061c6b11a8a78bcb`) and `google-sans-latin-ext-400-normal.woff2` (SHA-256 `9983057d2f73ea81748cfb9ba24a811c4bcc1d2c5bd479e779209706e5c13692`), retained as supplied. Retrieved November 7, 2026. Used for headings at weight 400, matching the funding tracker. License: `GoogleSans-OFL.txt` (SIL Open Font License 1.1).

Official project references: https://rsms.me/inter/ , https://github.com/adobe-fonts/source-sans , https://github.com/IBM/plex , https://github.com/adobe-fonts/source-serif .

## Chinese name fallback

`hpdi-name-kai.woff` is a web-only subset of LXGW WenKai Regular containing 王金震 (U+738B, U+91D1, U+9707). Source: https://github.com/lxgw/LxgwWenKai/blob/main/fonts/TTF/LXGWWenKai-Regular.ttf . Downloaded October 9, 2026 (America/New_York); converted and subsetted with FontTools without changing glyph outlines. Original family, copyright, and name records are retained. The accompanying `LXGWWenKai-OFL.txt` includes explicit permission for retaining reserved names in web-delivery subsets. Do not distribute this subset as an installable desktop font.

Source TTF SHA-256: `39ad71264b588165b469e35e6afb162a378dacd1f95348160240ba9038ac3009`.

## Chinese name: 行楷 / running script

`hpdi-name-xingkai.woff` is a web-delivery subset containing only 王金震 (U+738B, U+91D1, U+9707), made with FontTools without changing outlines. Source: https://github.com/google/fonts/blob/main/ofl/zhimangxing/ZhiMangXing-Regular.ttf . Downloaded October 10, 2026 (America/New_York). Zhi Mang Xing is a semi-cursive running script by Wei Zhimang; its original copyright/name metadata and accompanying `ZhiMangXing-OFL.txt` are retained. The shared name face prefers installed STXingkai/华文行楷, then this local subset. The former WenKai subset remains available as an archived asset and is no longer the active name font. Regenerate this subset if the Chinese name changes. No runtime CDN requests are made.

## Chinese name style comparisons

The existing WenKai and Zhi Mang Xing subsets provide 楷体 and 行楷 samples. `hpdi-name-cursive.woff` provides the 草书 sample, subsetted without changing outlines from https://github.com/google/fonts/blob/main/ofl/liujianmaocao/LiuJianMaoCao-Regular.ttf on October 10, 2026. It contains only 王金震 with original metadata preserved. Its companion `LiuJianMaoCao-OFL.txt` retains the copyright and SIL Open Font License. `assets/chinese-name-samples.png` is an exact rendered specimen of the bundled subsets, not a browser screenshot.
