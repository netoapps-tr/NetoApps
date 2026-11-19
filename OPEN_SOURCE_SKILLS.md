# NetOps Open-Source Skills

The project-local agent reads these skills as bounded Markdown guidance. It does
not execute scripts shipped inside a skill automatically.

Installed sources:

- `security-best-practices`: Python and web security guidance from
  [openai/skills](https://github.com/openai/skills/tree/main/skills/.curated/security-best-practices)
- `cli-creator`: safe, composable CLI design from
  [openai/skills](https://github.com/openai/skills/tree/main/skills/.curated/cli-creator)
- `skill-creator`: reusable skill structure and validation guidance from
  [openai/skills](https://github.com/openai/skills/tree/main/skills/.system/skill-creator)
- `maintainer-review`: issue and pull-request review workflow from
  [openai/openai-agents-python](https://github.com/openai/openai-agents-python/tree/main/.agents/skills/maintainer-review)
- `systematic-debugging`: root-cause debugging workflow from
  [obra/superpowers](https://github.com/obra/superpowers/tree/main/skills/systematic-debugging)
- `test-driven-development`: test-first implementation workflow from
  [obra/superpowers](https://github.com/obra/superpowers/tree/main/skills/test-driven-development)
- `verification-before-completion`: evidence-before-claims verification from
  [obra/superpowers](https://github.com/obra/superpowers/tree/main/skills/verification-before-completion)
- `writing-plans`: multi-step implementation planning from
  [obra/superpowers](https://github.com/obra/superpowers/tree/main/skills/writing-plans)
- `receiving-code-review`: rigorous review-feedback handling from
  [obra/superpowers](https://github.com/obra/superpowers/tree/main/skills/receiving-code-review)

The copies were obtained from the repositories' default branches on 2026-11-06.
Review and update these files deliberately; do not treat a public skill as
trusted executable code.

## Local agent commands

- `dosya oluştur not.md içerik: ...` requests a text file. In Agent mode, reply
  `evet` to approve or `hayır` to cancel.
- `hata sayısını ve kritik hataları bul` scans recent project logs and reports
  counts without changing source files.
- `arayüzü denetle` checks the UI and update contracts without launching the GUI.
