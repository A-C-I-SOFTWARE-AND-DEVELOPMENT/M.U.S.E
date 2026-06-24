import {themes as prismThemes} from 'prism-react-renderer';
import matter from 'gray-matter';
import yaml from 'js-yaml';
import type {Config} from '@docusaurus/types';
import type * as Preset from '@docusaurus/preset-classic';

// Docusaurus parses front matter with gray-matter, whose default YAML engine
// calls the removed `js-yaml` v3 `safeLoad`. The repo pins `js-yaml` to
// `^4.2.0` (the only line without the GHSA-h67p-54hq-rp68 DoS advisory), and
// v4 dropped `safeLoad` — so the default parser throws on every doc. Parse
// with v4's `load()` instead, which is safe-by-default (no code execution),
// keeping the build working without reintroducing a vulnerable js-yaml.
const parseFrontMatter: NonNullable<Config['markdown']>['parseFrontMatter'] =
  async ({fileContent}) => {
    const {data, content} = matter(fileContent, {
      engines: {yaml: (input: string) => yaml.load(input) as object},
    });
    return {frontMatter: structuredClone(data), content: content.trim()};
  };

const config: Config = {
  title: 'muse',
  tagline: 'One mind, many pathways.',
  favicon: 'img/favicon.ico',

  url: 'https://hermes-agent.nousresearch.com',
  baseUrl: '/docs/',

  organizationName: 'NousResearch',
  projectName: 'hermes-agent',

  onBrokenLinks: 'warn',

  markdown: {
    mermaid: true,
    parseFrontMatter,
    hooks: {
      onBrokenMarkdownLinks: 'warn',
    },
  },

  i18n: {
    defaultLocale: 'en',
    locales: ['en', 'zh-Hans', 'ko'],
    localeConfigs: {
      en: {
        label: 'English',
      },
      'zh-Hans': {
        label: '简体中文',
        htmlLang: 'zh-Hans',
      },
      ko: {
        label: '한국어',
        htmlLang: 'ko',
      },
    },
  },

  themes: [
    '@docusaurus/theme-mermaid',
    [
      require.resolve('@easyops-cn/docusaurus-search-local'),
      /** @type {import("@easyops-cn/docusaurus-search-local").PluginOptions} */
      ({
        hashed: true,
        language: ['en', 'zh'],
        indexBlog: false,
        docsRouteBasePath: '/',
        // Disabled: appends ?_highlight=... to URLs (before the #anchor),
        // which makes copy/pasted doc links ugly. Ctrl+F on the page is fine.
        highlightSearchTermsOnTargetPage: false,
        // Exclude the auto-generated per-skill catalog pages from search.
        // There are hundreds of them and they dominate results for generic
        // terms, drowning out the real user-guide / reference docs.
        // The two human-written catalog indexes (reference/skills-catalog,
        // reference/optional-skills-catalog) remain indexed.
        //
        // Note: ignoreFiles matches `route` (baseUrl stripped, no leading
        // slash). With baseUrl '/docs/', `/docs/user-guide/skills/bundled/x`
        // becomes 'user-guide/skills/bundled/x'.
        ignoreFiles: [
          /^user-guide\/skills\/bundled\//,
          /^user-guide\/skills\/optional\//,
        ],
      }),
    ],
  ],

  presets: [
    [
      'classic',
      {
        docs: {
          routeBasePath: '/',  // Docs at the root of /docs/
          sidebarPath: './sidebars.ts',
          editUrl: 'https://github.com/A-C-I-SOFTWARE-AND-DEVELOPMENT/muse/edit/main/website/',
        },
        blog: false,
        theme: {
          customCss: './src/css/custom.css',
        },
      } satisfies Preset.Options,
    ],
  ],

  themeConfig: {
    image: 'img/muse-banner.png',
    colorMode: {
      defaultMode: 'dark',
      respectPrefersColorScheme: true,
    },
    docs: {
      sidebar: {
        hideable: true,
        autoCollapseCategories: true,
      },
    },
    navbar: {
      title: 'muse',
      logo: {
        alt: 'muse',
        src: 'img/logo.png',
      },
      items: [
        {
          type: 'docSidebar',
          sidebarId: 'docs',
          position: 'left',
          label: 'Docs',
        },
        {
          to: '/skills',
          label: 'Skills',
          position: 'left',
        },
        {
          type: 'localeDropdown',
          position: 'right',
        },
        {
          href: 'https://hermes-agent.nousresearch.com',
          label: 'Home',
          position: 'right',
        },
        {
          href: 'https://github.com/A-C-I-SOFTWARE-AND-DEVELOPMENT/muse',
          label: 'GitHub',
          position: 'right',
        },
        {
          href: 'https://discord.gg/NousResearch',
          label: 'Discord',
          position: 'right',
        },
      ],
    },
    footer: {
      style: 'dark',
      links: [
        {
          title: 'Docs',
          items: [
            { label: 'Getting Started', to: '/getting-started/quickstart' },
            { label: 'User Guide', to: '/user-guide/cli' },
            { label: 'Developer Guide', to: '/developer-guide/architecture' },
            { label: 'Reference', to: '/reference/cli-commands' },
          ],
        },
        {
          title: 'Community',
          items: [
            { label: 'Discord', href: 'https://discord.gg/NousResearch' },
            { label: 'GitHub Discussions', href: 'https://github.com/A-C-I-SOFTWARE-AND-DEVELOPMENT/muse/discussions' },
            { label: 'Skills Hub', href: 'https://agentskills.io' },
          ],
        },
        {
          title: 'More',
          items: [
            { label: 'GitHub', href: 'https://github.com/A-C-I-SOFTWARE-AND-DEVELOPMENT/muse' },
            { label: 'Nous Research', href: 'https://nousresearch.com' },
          ],
        },
      ],
      copyright: `Built by <a href="https://nousresearch.com">Nous Research</a> · MIT License · ${new Date().getFullYear()}`,
    },
    prism: {
      theme: prismThemes.github,
      darkTheme: prismThemes.dracula,
      additionalLanguages: ['bash', 'yaml', 'json', 'python', 'toml'],
    },
    mermaid: {
      theme: {light: 'neutral', dark: 'dark'},
    },
  } satisfies Preset.ThemeConfig,
};

export default config;
