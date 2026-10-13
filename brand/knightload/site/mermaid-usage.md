# Knightload Mermaid theme — usage (ISI-5791 / WS-1)

On-brand Mermaid palette for the Signal Diamond brand. Two consumption paths.

## 1. Docusaurus site (`@docusaurus/theme-mermaid`)

Docusaurus renders Mermaid live and already switches with the color mode. Point the
two themeVariables sets from `mermaid-theme.json` at light/dark in `docusaurus.config`:

```js
// npm i @docusaurus/theme-mermaid ; markdown.mermaid = true ; themes:['@docusaurus/theme-mermaid']
const kl = require('./static/img/mermaid-theme.json'); // or wherever WS-2 places it
themeConfig: {
  mermaid: {
    theme: { light: 'base', dark: 'base' },
    options: kl.dark.themeVariables, // Docusaurus applies one set; use dark (brand key)
  },
}
```

Docusaurus applies a single `options` object regardless of color mode, so use the
**dark** set (the brand's native key) and let the `base` theme + transparent
backgrounds sit on the page surface. For true per-mode variables, WS-2 can inject
`light`/`dark` via a small client module keyed on `[data-theme]`.

## 2. Raw GitHub / README (`%%{init}%%`)

GitHub renders Mermaid but has no Knightload theme — prepend an init directive to each
diagram. Dark variant (GitHub READMEs render on a dark-ish surface):

```
%%{init: {"theme":"base","themeVariables":{"darkMode":true,"background":"transparent","fontFamily":"'Space Grotesk','Sora','Segoe UI',system-ui,sans-serif","primaryColor":"#212E50","primaryTextColor":"#C7CDD6","primaryBorderColor":"#2EE6D6","secondaryColor":"#1A1A2E","secondaryTextColor":"#C7CDD6","secondaryBorderColor":"#96A0B2","tertiaryColor":"#16213E","tertiaryTextColor":"#C7CDD6","tertiaryBorderColor":"#96A0B2","lineColor":"#2EE6D6","textColor":"#C7CDD6","mainBkg":"#212E50","nodeBorder":"#2EE6D6","clusterBkg":"#16213E","clusterBorder":"#96A0B2","titleColor":"#C7CDD6","edgeLabelBackground":"#16213E","nodeTextColor":"#C7CDD6","noteBkgColor":"#FFB23E","noteTextColor":"#16213E","noteBorderColor":"#FFB23E","actorBkg":"#212E50","actorBorder":"#2EE6D6","actorTextColor":"#C7CDD6","actorLineColor":"#96A0B2","signalColor":"#C7CDD6","signalTextColor":"#C7CDD6","labelBoxBkgColor":"#1A1A2E","labelBoxBorderColor":"#2EE6D6","labelTextColor":"#C7CDD6","loopTextColor":"#C7CDD6","activationBkgColor":"#2EE6D6","activationBorderColor":"#2EE6D6","errorBkgColor":"#FFB23E","errorTextColor":"#16213E"}} }%%
flowchart LR
  A[Model] --> B{Engine} --> C[k6 / JMeter / Locust / Gatling]
```

(The light variant — `initLight` in `mermaid-theme.json` — is available for light
contexts.) Keep the directive on the first line of the code block.

## Palette reference

| token | hex | role |
|---|---|---|
| indigo-0 | #1A1A2E | darkest night / page bg |
| indigo-1 | #16213E | indigo surface / node fill-dark |
| indigo-2 | #212E50 | raised node fill |
| silver | #C7CDD6 | text on dark |
| teal | #2EE6D6 | primary accent / edges (dark) |
| amber | #FFB23E | notes / callouts / errors |
| mute | #96A0B2 | secondary borders / labels |

Edges/lines use **teal** on dark and **indigo** on light; notes use **amber**.
