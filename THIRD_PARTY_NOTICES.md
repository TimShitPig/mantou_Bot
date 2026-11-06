# Third-party notices

## chatgpt2api v3.2.4

Source: https://github.com/yukkcat/chatgpt2api/releases/tag/v3.2.4
Commit: `72446e2d8d3a21fac5c9aa2d96addd37d6970326`
License: GNU Affero General Public License version 3 only (AGPL-3.0-only), see this repository's LICENSE.

The ZLibrary account manager layout and interaction design are adapted from `web-vue/src/views/Accounts.vue` and its account table / action / bulk-action components. This project implements the adapted interface in its existing native HTML/CSS/JavaScript modules, with ZLibrary-specific account operations. It does not incorporate the upstream Vue runtime or represent unsupported ChatGPT credential/quota fields as ZLibrary data.

ZLibrary automatic pool selection also follows the eligible-candidate cursor round-robin design of `services/account_service.py` (`_acquire_next_candidate_token`, `get_text_access_token`). Quota exhaustion is displayed as 限流; ZLibrary-specific verification, persistence, and download binding remain local implementations.

Original distribution notice follows:

```text
ChatGPT2API Notices

Copyright (C) 2026 yukkcat and contributors.

The current ChatGPT2API distribution is licensed under the GNU Affero
General Public License version 3 only (AGPL-3.0-only). See LICENSE.

Upstream MIT-licensed code
--------------------------

This project includes code derived from basketikun/chatgpt2api:
https://github.com/basketikun/chatgpt2api

The upstream code remains subject to the following notice and license. Code
covered by that notice may continue to be used under its original MIT terms.

MIT License

Copyright (c) 2026 kunkun

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

```
