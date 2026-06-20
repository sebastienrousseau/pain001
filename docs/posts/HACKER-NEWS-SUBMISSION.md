<!-- SPDX-License-Identifier: Apache-2.0 OR MIT -->

# Hacker News submission template

When you're ready to post the blog (`2026-06-21-lessons-from-shipping-a-100pc-coverage-payment-library.md`)
to Hacker News:

## Title (≤ 80 chars; HN truncates harder than that)

```
Show HN: Lessons from shipping a 100% coverage ISO 20022 payment library
```

Alternates if the above feels too long after publishing:

- `Lessons from shipping a 100% coverage payment library`
- `Pain001 v0.0.53: a 100% coverage ISO 20022 payment suite`
- `Show HN: A coordinated-release 4-package ISO 20022 suite (Python)`

## URL

Point to the blog post on whatever you publish to:

- If on your own domain: `https://sebastienrousseau.com/posts/lessons-from-100pc-coverage`
- If on GitHub Pages: `https://sebastienrousseau.github.io/pain001/posts/2026-06-21-lessons-from-shipping-a-100pc-coverage-payment-library.html`
- If on Substack / Dev.to / Medium: the canonical post URL

**Pick one URL and stick with it.** HN dedupes by URL; if you've
already submitted a similar URL before, it gets quietly marked
"duplicate" and never reaches the front page.

## When to post

**Tuesday or Wednesday, 9am UTC** (≈ 5am US East / 2am US West /
10am London / 5pm Tokyo). That's the peak overlap of European
morning + US morning. Posts at this window reliably outperform
weekend posts 3-5x on the same content.

Avoid:
- Friday afternoon (US, dead zone)
- Saturday / Sunday (engaged-reader crowd shrinks)
- Holidays (Memorial Day, July 4, Thanksgiving week, Dec 22 - Jan 3)

## First-comment template

Within 30 seconds of posting, post the *first comment yourself* —
this acts as a "what to talk about" prompt and reliably 2x's the
engagement. Don't editorialise; ask a question.

```
Author here. Three things I'm genuinely uncertain about and would
love this crowd's pushback on:

1. The pragma rule. I require every `# pragma: no cover` to carry
   a one-line justification. In ~3000 lines I have 11 of them.
   Is that the right shape, or am I over-thinking the "is 100%
   meaningful?" question?

2. The plugin contract. I went 53 patch releases before formalising
   it, then had to migrate every existing loader/scheme/writer.
   Should plugin substrates be in the v0.0.1 of any infrastructure
   library that wants to outlive its first maintainer?

3. The bus factor. I've been "inviting" co-maintainers in
   GOVERNANCE.md for >1 year and that's done nothing. Today I
   sent the first concrete recruitment DM. Has anyone successfully
   recruited an OSS co-maintainer? What worked?

Repo: https://github.com/sebastienrousseau/pain001
Suite: https://pypi.org/project/pain001/ + pain001-mcp + pain001-lsp + pain001-loader-xlsx
```

## What to do during the post's first hour

The post lives or dies in the first 60 minutes. After that, HN's
ranking algorithm caps how high it can climb without a sustained
upvote rate.

Open the post in a tab and refresh it every 5-10 min. Reply to
every top-level comment within 15 min. **Don't be defensive.**
HN rewards "you're right, I should clarify that" far more than
"actually, you've misunderstood." If a critic has a point, say so
in public and update the post (note: "edit:" with a timestamp).

## What NOT to do

- **Don't post to /r/programming, Twitter, LinkedIn at the same
  time** — HN penalises posts that look like coordinated drives.
  Stagger: HN first, Twitter/LinkedIn 6-12 hours later once HN
  ranking is established.
- **Don't ask friends to upvote.** HN's spam detection is good;
  detected coordinated voting drops the post permanently.
- **Don't link to your repo, your Twitter, or anything else in
  the body of the post.** HN strips most of those anyway, and the
  ones that survive read as self-promotion. Links go in the first
  comment, not the post.

## After the post

Within 48 hours, regardless of whether it hits front page:

1. **Update the post's "companion HN thread" link** with the
   actual HN URL (currently `#` placeholder).
2. **Update the project README** with a "Pain001 was on Hacker
   News today: [link]" line — drives a second wave of traffic.
3. **Open one issue per genuine criticism** from the HN comments.
   They're the most-rigorous critique you'll get for free; honour
   them with action.

## Submission tracker

| Field | Value |
| :--- | :--- |
| Posted at | _2026-MM-DD HH:MM UTC_ |
| HN URL | _https://news.ycombinator.com/item?id=..._ |
| Peak rank | _#__ on front page_ |
| Upvotes after 24h | _N_ |
| Top critique to act on | _summary_ |

Fill in once posted.
