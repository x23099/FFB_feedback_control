# インタラクティブ開発マルチエージェント 成果物レポート

## 👑 確定開発計画書 (マネージャー & ユーザー合意)
# 計画書

## 1. 目的
- 何を実現したいか: Chromeのタブをユーザー定義グループで管理し、ブラウザ再起動後も自動復元できるChrome拡張機能を開発する
- 期待する効果: タブの多さによる認知負荷を軽減し、作業コンテキストを素早く切り替え・復元できる
- 成功条件: グループの作成・タブの追加削除・グループ名編集・削除・自動分類提案が動作し、Chrome再起動後にグループとタブが復元されること

## 2. 背景
- 現状: Chromeネイティブのタブグループ機能は再起動後に消えるケースがあり、セッション復元が不安定
- 課題: 複数の作業コンテキスト（仕事・調査・SNSなど）を跨ぐタブ群を、再起動をまたいで維持する手段がない
- 変更理由: 既存ツールではなくオリジナル実装により、自分のユースケースに完全最適化したい

## 3. 要件

### 必須要件
- グループを手動で作成・命名できる
- 現在開いているタブを任意のグループに追加・削除できる
- グループ名を編集・グループ自体を削除できる
- Chromeを閉じて再起動した際に、保存済みグループのタブを自動復元できる
- グループ・タブ情報をchrome.storage.localで永続化する

### できれば欲しい要件
- URLのドメイン・キーワードを元にタブの自動分類を「提案」する機能（提案ボタン押下時に動作）
- グループ単位でタブを一括開く・閉じる操作

### 非要件
- 性能: 高速処理は不要。タブ数100以下を想定
- セキュリティ: Chromeウェブストアへの公開なし。個人利用のためストアポリシー準拠は不要だが、過剰なpermissions要求はしない
- 保守性: チーム開発・CI/CD不要。単一開発者前提
- UI/UX: デザインの洗練度は低優先。機能動作優先
- 同期: chrome.storage.syncによるデバイス間同期は対象外

## 4. 変更範囲
- 対象: Chrome拡張機能の新規フルスクラッチ開発（manifest.json / popup / background / storage）
- 対象外: Webサーバー・外部API・既存サービスとの連携・モバイル対応

## 5. 実装方針
- 方針: Manifest V3準拠。Vanilla JS（フレームワークなし）でポップアップUIを構築。chrome.storage.localでグループ・タブデータを永続化。background Service WorkerでChrome起動時の自動復元を制御する
- 採用理由: 中級者（Chrome拡張機能初挑戦）の学習コストを最小化するため、依存ライブラリゼロ構成を選択。Manifest V3はChromeの現行標準であり、今後の互換性リスクを排除できる
- 代替案と不採用理由:
  - React/Vue採用 → ビルド環境が必要でChrome拡張機能初挑戦には過剰。不採用
  - chrome.storage.sync採用 → デバイス間同期は非要件。容量制限（100KB）もリスクになるため不採用
  - Manifest V2採用 → Chromeが段階廃止予定のため不採用

## 6. タスク分割

| 順番 | 担当 | タスク | 入力 | 出力 | 完了条件 |
|---|---|---|---|---|---|
| 1 | 開発者 | プロジェクト構成・manifest.json作成 | 本計画書 | ディレクトリ構成・manifest.json | Chromeの拡張機能管理画面でロード成功 |
| 2 | 開発者 | chrome.storage.local データ設計 | グループ・タブの要件 | ストレージスキーマ定義（JSON構造） | スキーマが全必須要件を網羅していること |
| 3 | 開発者 | ポップアップUI実装（グループ一覧表示・作成） | スキーマ定義 | popup.html / popup.js / popup.css | グループ作成・一覧表示が動作すること |
| 4 | 開発者 | タブ追加・削除機能実装 | popup.js・chrome.tabs API | タブ操作機能 | 現在開いているタブを任意グループに追加・削除できること |
| 5 | 開発者 | グループ名編集・削除機能実装 | popup.js・ストレージ | 編集・削除UI | グループ名変更・グループ削除が即時反映されること |
| 6 | 開発者 | 自動分類提案機能実装 | chrome.tabs API・URLドメイン情報 | 提案ロジック・UIボタン | ボタン押下でタブのグループ案が表示されること |
| 7 | 開発者 | 再起動時自動復元機能実装 | background.js・chrome.runtime.onStartup | Service Worker・復元ロジック | Chrome再起動後に保存グループのタブが自動で開くこと |
| 8 | 開発者 | 結合テスト・バグ修正 | 全実装済みコード | 動作確認済み拡張機能 | 受け入れ条件7項目が全て通過すること |

## 7. 受け入れ条件
- グループを新規作成し、任意の名前をつけられること
- 現在開いているタブをグループに追加できること
- グループからタブを削除できること
- グループ名を編集できること
- グループを削除できること
- 「自動分類提案」ボタンを押すと、ドメイン単位でタブのグループ案が表示されること
- Chromeを完全終了して再起動した際、保存済みグループのタブが自動で復元されること

## 8. リスク

| リスク | 影響 | 対策 |
|---|---|---|
| chrome.runtime.onStartupが発火しないケース（クラッシュ終了など） | 自動復元が動作しない | chrome.runtime.onInstalledとの併用、またはポップアップに「手動復元」ボタンを追加 |
| 復元時にタブを大量に開いてブラウザが重くなる | UX劣化 | 復元タブ数に上限設定（例：20タブ/グループ）を検討 |
| chrome.storage.localの容量上限（5MB）超過 | データ保存失敗 | 個人利用・100タブ以下想定のため当面問題なし。超過時はエラー通知を実装 |
| Manifest V3のService Worker制限（非アクティブ時終了） | バックグラウンド処理の不安定動作 | 起動時イベント（onStartup）のみに処理を限定し、常駐処理を排除することで回避 |

## 9. 未確定事項
- 自動分類提案のロジック詳細（ドメイン単位のみか、ページタイトルのキーワードも使うか）
- タブ復元時の動作：新しいウィンドウで開くか、現在のウィンドウに追加するか
- グループごとの復元ON/OFFを個別に切り替える機能の要否

## 10. 承認
- あなたの確認: 未承認
- マネージャー確認: 承認済み
- エンジニア確認: 未承認

---

## 🎨 フロントエンド実装・設計
# Chrome拡張機能「TabGroup Manager」実装ドキュメント

---

## 目次
1. ディレクトリ構成
2. UI/UX構造設計
3. コンポーネント構成
4. 実装コード（全ファイル）
5. コード解説

---

## 1. ディレクトリ構成

```
tab-group-manager/
├── manifest.json          # 拡張機能の設定ファイル
├── background.js          # Service Worker（起動時復元）
├── popup/
│   ├── popup.html         # ポップアップUI
│   ├── popup.css          # スタイル
│   └── popup.js           # UIロジック
├── js/
│   ├── storage.js         # ストレージ操作モジュール
│   ├── tabManager.js      # タブ操作モジュール
│   └── classifier.js      # 自動分類提案モジュール
└── icons/
    ├── icon16.png
    ├── icon48.png
    └── icon128.png
```

---

## 2. UI/UX構造設計

```
┌─────────────────────────────────────────┐
│  🗂 TabGroup Manager          [設定⚙]  │
│─────────────────────────────────────────│
│  [+ 新しいグループを作成]  [🔮 自動提案] │
│─────────────────────────────────────────│
│  📁 仕事                      [▼] [⋯]  │
│  ├─ ● GitHub - Pull Request     [×]    │
│  ├─ ● Notion - 設計書           [×]    │
│  └─ [現在のタブを追加 +]               │
│─────────────────────────────────────────│
│  📁 調査                      [▼] [⋯]  │
│  ├─ ● MDN Web Docs             [×]    │
│  └─ [現在のタブを追加 +]               │
│─────────────────────────────────────────│
│  [全グループを復元] [全グループを閉じる] │
└─────────────────────────────────────────┘

[⋯]メニュー展開時:
┌─────────────────┐
│ ✏ グループ名を編集│
│ 📂 全タブを開く  │
│ 📕 全タブを閉じる│
│ 🗑 グループを削除 │
└─────────────────┘

[🔮 自動提案]押下時:
┌─────────────────────────────────────────┐
│  🔮 自動分類提案                  [×]  │
│─────────────────────────────────────────│
│  以下のグループ構成を提案します：        │
│                                         │
│  📁 github.com (3タブ)                  │
│  📁 google.com (2タブ)                  │
│  📁 その他 (5タブ)                      │
│                                         │
│  [この提案を適用]        [キャンセル]   │
└─────────────────────────────────────────┘
```

---

## 3. コンポーネント構成

```
PopupApp (popup.js)
├── Header
│   ├── AppTitle
│   └── SettingsButton
├── ActionBar
│   ├── CreateGroupButton
│   └── AutoClassifyButton
├── GroupList
│   └── GroupCard (×n)
│       ├── GroupHeader
│       │   ├── GroupName
│       │   ├── CollapseToggle
│       │   └── GroupMenuButton
│       │       └── GroupMenu (dropdown)
│       │           ├── RenameMenuItem
│       │           ├── OpenAllMenuItem
│       │           ├── CloseAllMenuItem
│       │           └── DeleteMenuItem
│       └── TabList
│           ├── TabItem (×n)
│           │   ├── TabFavicon
│           │   ├── TabTitle
│           │   └── RemoveTabButton
│           └── AddCurrentTabButton
├── FooterActions
│   ├── RestoreAllButton
│   └── CloseAllGroupsButton
└── AutoClassifyModal
    ├── ProposalList
    │   └── ProposalItem (×n)
    ├── ApplyButton
    └── CancelButton
```

---

## 4. 実装コード

### 4-1. `manifest.json`

```json
{
  "manifest_version": 3,
  "name": "TabGroup Manager",
  "version": "1.0.0",
  "description": "タブをユーザー定義グループで管理し、再起動後も自動復元できるChrome拡張機能",

  "permissions": [
    "tabs",
    "storage"
  ],

  "action": {
    "default_popup": "popup/popup.html",
    "default_icon": {
      "16":  "icons/icon16.png",
      "48":  "icons/icon48.png",
      "128": "icons/icon128.png"
    },
    "default_title": "TabGroup Manager"
  },

  "background": {
    "service_worker": "background.js",
    "type": "module"
  },

  "icons": {
    "16":  "icons/icon16.png",
    "48":  "icons/icon48.png",
    "128": "icons/icon128.png"
  }
}
```

---

### 4-2. `js/storage.js`（ストレージモジュール）

```javascript
/**
 * storage.js
 * chrome.storage.local の操作を抽象化するモジュール
 *
 * データスキーマ:
 * {
 *   groups: {
 *     [groupId: string]: {
 *       id: string,          // UUID
 *       name: string,        // グループ名
 *       color: string,       // 表示色（HEX）
 *       collapsed: boolean,  // 折りたたみ状態
 *       createdAt: number,   // 作成日時（Unix ms）
 *       tabs: [
 *         {
 *           id: string,      // タブ識別UUID（Chrome tabIdとは別）
 *           url: string,     // タブURL
 *           title: string,   // タブタイトル
 *           favicon: string, // faviconURL
 *           addedAt: number  // 追加日時（Unix ms）
 *         }
 *       ]
 *     }
 *   },
 *   settings: {
 *     autoRestoreOnStartup: boolean,  // 起動時自動復元
 *     maxRestoreTabsPerGroup: number  // グループごとの復元上限
 *   }
 * }
 */

const STORAGE_KEY = 'tabGroupManager';

/**
 * ストレージから全データを取得する
 * @returns {Promise<{groups: Object, settings: Object}>}
 */
export async function loadData() {
  return new Promise((resolve) => {
    chrome.storage.local.get(STORAGE_KEY, (result) => {
      const data = result[STORAGE_KEY] || {};
      resolve({
        groups: data.groups || {},
        settings: data.settings || getDefaultSettings()
      });
    });
  });
}

/**
 * ストレージに全データを保存する
 * @param {{groups: Object, settings: Object}} data
 * @returns {Promise<void>}
 */
export async function saveData(data) {
  return new Promise((resolve, reject) => {
    chrome.storage.local.set({ [STORAGE_KEY]: data }, () => {
      if (chrome.runtime.lastError) {
        reject(new Error(chrome.runtime.lastError.message));
      } else {
        resolve();
      }
    });
  });
}

/**
 * グループ一覧を取得する（配列形式・作成日時順）
 * @returns {Promise<Array>}
 */
export async function getGroups() {
  const data = await loadData();
  return Object.values(data.groups)
    .sort((a, b) => a.createdAt - b.createdAt);
}

/**
 * グループを新規作成する
 * @param {string} name - グループ名
 * @param {string} [color='#4f8ef7'] - 表示色
 * @returns {Promise<Object>} 作成されたグループ
 */
export async function createGroup(name, color = '#4f8ef7') {
  const data = await loadData();
  const group = {
    id: generateId(),
    name: name.trim(),
    color,
    collapsed: false,
    createdAt: Date.now(),
    tabs: []
  };
  data.groups[group.id] = group;
  await saveData(data);
  return group;
}

/**
 * グループを更新する（部分更新対応）
 * @param {string} groupId
 * @param {Object} updates - 更新するフィールド
 * @returns {Promise<Object>} 更新後のグループ
 */
export async function updateGroup(groupId, updates) {
  const data = await loadData();
  if (!data.groups[groupId]) {
    throw new Error(`Group not found: ${groupId}`);
  }
  data.groups[groupId] = { ...data.groups[groupId], ...updates };
  await saveData(data);
  return data.groups[groupId];
}

/**
 * グループを削除する
 * @param {string} groupId
 * @returns {Promise<void>}
 */
export async function deleteGroup(groupId) {
  const data = await loadData();
  delete data.groups[groupId];
  await saveData(data);
}

/**
 * グループにタブを追加する
 * @param {string} groupId
 * @param {{url: string, title: string, favicon: string}} tabInfo
 * @returns {Promise<Object>} 追加されたタブオブジェクト
 */
export async function addTabToGroup(groupId, tabInfo) {
  const data = await loadData();
  if (!data.groups[groupId]) {
    throw new Error(`Group not found: ${groupId}`);
  }

  // 同一URLの重複チェック
  const exists = data.groups[groupId].tabs.some(t => t.url === tabInfo.url);
  if (exists) {
    throw new Error('このタブはすでにグループに追加されています');
  }

  const tab = {
    id: generateId(),
    url: tabInfo.url,
    title: tabInfo.title || tabInfo.url,
    favicon: tabInfo.favicon || '',
    addedAt: Date.now()
  };

  data.groups[groupId].tabs.push(tab);
  await saveData(data);
  return tab;
}

/**
 * グループからタブを削除する
 * @param {string} groupId
 * @param {string} tabId - ストレージ上のタブID
 * @returns {Promise<void>}
 */
export async function removeTabFromGroup(groupId, tabId) {
  const data = await loadData();
  if (!data.groups[groupId]) {
    throw new Error(`Group not found: ${groupId}`);
  }
  data.groups[groupId].tabs = data.groups[groupId].tabs.filter(t => t.id !== tabId);
  await saveData(data);
}

/**
 * 複数グループを一括保存する（自動提案の適用に使用）
 * @param {Array<{name: string, tabs: Array}>} groupsArray
 * @returns {Promise<void>}
 */
export async function bulkCreateGroups(groupsArray) {
  const data = await loadData();
  const COLORS = ['#4f8ef7', '#f7874f', '#4ff78e', '#f74f8e', '#8e4ff7', '#f7d44f'];

  groupsArray.forEach((g, index) => {
    const group = {
      id: generateId(),
      name: g.name,
      color: COLORS[index % COLORS.length],
      collapsed: false,
      createdAt: Date.now() + index, // 順序保証のためmsをずらす
      tabs: g.tabs.map(t => ({
        id: generateId(),
        url: t.url,
        title: t.title || t.url,
        favicon: t.favicon || '',
        addedAt: Date.now()
      }))
    };
    data.groups[group.id] = group;
  });

  await saveData(data);
}

/**
 * デフォルト設定を返す
 * @returns {Object}
 */
function getDefaultSettings() {
  return {
    autoRestoreOnStartup: true,
    maxRestoreTabsPerGroup: 20
  };
}

/**
 * 簡易UUID生成
 * @returns {string}
 */
function generateId() {
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 9)}`;
}
```

---

### 4-3. `js/tabManager.js`（タブ操作モジュール）

```javascript
/**
 * tabManager.js
 * Chrome Tabs API を抽象化するモジュール
 */

/**
 * 現在アクティブなタブの情報を取得する
 * @returns {Promise<{url: string, title: string, favicon: string}>}
 */
export async function getCurrentTab() {
  return new Promise((resolve, reject) => {
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      if (chrome.runtime.lastError) {
        reject(new Error(chrome.runtime.lastError.message));
        return;
      }
      if (!tabs || tabs.length === 0) {
        reject(new Error('アクティブなタブが見つかりません'));
        return;
      }
      const tab = tabs[0];
      resolve({
        url: tab.url || '',
        title: tab.title || tab.url || '',
        favicon: tab.favIconUrl || ''
      });
    });
  });
}

/**
 * 全タブの情報を取得する（chrome:// などの内部URLを除外）
 * @returns {Promise<Array<{url: string, title: string, favicon: string}>>}
 */
export async function getAllTabs() {
  return new Promise((resolve, reject) => {
    chrome.tabs.query({ currentWindow: true }, (tabs) => {
      if (chrome.runtime.lastError) {
        reject(new Error(chrome.runtime.lastError.message));
        return;
      }
      const filteredTabs = (tabs || [])
        .filter(tab => tab.url && isRestorable(tab.url))
        .map(tab => ({
          url: tab.url,
          title: tab.title || tab.url,
          favicon: tab.favIconUrl || ''
        }));
      resolve(filteredTabs);
    });
  });
}

/**
 * URLを新しいタブで開く
 * @param {string} url
 * @param {boolean} [active=false] - アクティブにするか
 * @returns {Promise<chrome.tabs.Tab>}
 */
export async function openTab(url, active = false) {
  return new Promise((resolve, reject) => {
    chrome.tabs.create({ url, active }, (tab) => {
      if (chrome.runtime.lastError) {
        reject(new Error(chrome.runtime.lastError.message));
        return;
      }
      resolve(tab);
    });
  });
}

/**
 * タブ配列を順次開く（復元処理・一括展開に使用）
 * @param {Array<{url: string}>} tabs
 * @param {number} [maxTabs=20] - 最大展開数
 * @returns {Promise<{opened: number, skipped: number}>}
 */
export async function openTabsBatch(tabs, maxTabs = 20) {
  const targetTabs = tabs.slice(0, maxTabs);
  const skipped = tabs.length - targetTabs.length;
  let opened = 0;

  for (const tab of targetTabs) {
    if (!tab.url || !isRestorable(tab.url)) continue;
    try {
      await openTab(tab.url, false);
      opened++;
      // Chrome への負荷を抑えるため少し待機
      await sleep(50);
    } catch (e) {
      console.warn(`タブを開けませんでした: ${tab.url}`, e);
    }
  }

  return { opened, skipped };
}

/**
 * 現在開いているタブのURLセットを取得する
 * @returns {Promise<Set<string>>}
 */
export async function getOpenTabUrls() {
  const tabs = await getAllTabs();
  return new Set(tabs.map(t => t.url));
}

/**
 * URLが復元可能かチェックする（chrome:// や about: を除外）
 * @param {string} url
 * @returns {boolean}
 */
export function isRestorable(url) {
  if (!url) return false;
  const blocklist = ['chrome://', 'chrome-extension://', 'about:', 'edge://', 'data:'];
  return !blocklist.some(prefix => url.startsWith(prefix));
}

/**
 * 指定ミリ秒待機する
 * @param {number} ms
 * @returns {Promise<void>}
 */
function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}
```

---

### 4-4. `js/classifier.js`（自動分類提案モジュール）

```javascript
/**
 * classifier.js
 * タブの自動分類提案ロジック
 *
 * 分類戦略:
 * 1. URLのドメイン（hostname）でグルーピング
 * 2. タイトルの共通キーワードでサブグルーピング（拡張機能付き）
 * 3. 2タブ未満のドメインは「その他」にまとめる
 */

/**
 * タブ配列からグループ案を生成する
 * @param {Array<{url: string, title: string, favicon: string}>} tabs
 * @returns {Array<{name: string, tabs: Array, reason: string}>}
 */
export function classifyTabs(tabs) {
  if (!tabs || tabs.length === 0) return [];

  // ステップ1: ドメイン単位でグルーピング
  const domainMap = groupByDomain(tabs);

  // ステップ2: ドメイングループを提案に変換
  const proposals = [];
  const singletonTabs = []; // ドメインが1タブだけのもの

  for (const [domain, domainTabs] of Object.entries(domainMap)) {
    if (domainTabs.length >= 2) {
      // ステップ3: ドメイン名を人間が読みやすい形に変換
      const groupName = domainToGroupName(domain);

      // ステップ4: 同ドメイン内でタイトルキーワードによるサブ分類を試みる
      const subGroups = trySubClassify(domainTabs, groupName);
      proposals.push(...subGroups);
    } else {
      singletonTabs.push(...domainTabs);
    }
  }

  // ステップ5: 1タブだけのドメインを「その他」にまとめる
  if (singletonTabs.length > 0) {
    proposals.push({
      name: 'その他',
      tabs: singletonTabs,
      reason: `${singletonTabs.length}件のタブ（各ドメイン1タブ）`
    });
  }

  // ステップ6: タブ数の多い順にソート
  return proposals.sort((a, b) => b.tabs.length - a.tabs.length);
}

/**
 * タブをドメイン単位でグルーピングする
 * @param {Array} tabs
 * @returns {Object} { domain: tabs[] }
 */
function groupByDomain(tabs) {
  const map = {};
  for (const tab of tabs) {
    const domain = extractDomain(tab.url);
    if (!domain) continue;
    if (!map[domain]) map[domain] = [];
    map[domain].push(tab);
  }
  return map;
}

/**
 * URLからドメインを抽出する
 * @param {string} url
 * @returns {string}
 */
function extractDomain(url) {
  try {
    const { hostname } = new URL(url);
    // www. を除去してメインドメインを取得
    return hostname.replace(/^www\./, '');
  } catch {
    return '';
  }
}

/**
 * ドメイン文字列をグループ名に変換する
 * @param {string} domain - 例: "github.com"
 * @returns {string} - 例: "GitHub"
 */
function domainToGroupName(domain) {
  // 既知ドメインの人間可読名マッピング
  const knownDomains = {
    'github.com':         'GitHub',
    'gitlab.com':         'GitLab',
    'google.com':         'Google',
    'google.co.jp':       'Google',
    'youtube.com':        'YouTube',
    'twitter.com':        'Twitter / X',
    'x.com':              'Twitter / X',
    'notion.so':          'Notion',
    'stackoverflow.com':  'Stack Overflow',
    'qiita.com':          'Qiita',
    'zenn.dev':           'Zenn',
    'mdn.mozilla.org':    'MDN',
    'docs.google.com':    'Google Docs',
    'mail.google.com':    'Gmail',
    'reddit.com':         'Reddit',
    'amazon.co.jp':       'Amazon',
    'amazon.com':         'Amazon',
    'slack.com':          'Slack',
    'linear.app':         'Linear',
    'figma.com':          'Figma',
    'vercel.com':         'Vercel',
    'netlify.com':        'Netlify'
  };

  if (knownDomains[domain]) return knownDomains[domain];

  // 未知ドメインはドメイン名をPascalCase的に整形
  const parts = domain.split('.');
  const mainPart = parts[0];
  return mainPart.charAt(0).toUpperCase() + mainPart.slice(1);
}

/**
 * 同ドメイン内のタブをタイトルキーワードでサブ分類を試みる
 * 3タブ以上あり、かつ明確な共通キーワードがある場合のみ分割する
 * @param {Array} tabs
 * @param {string} baseName
 * @returns {Array<{name: string, tabs: Array, reason: string}>}
 */
function trySubClassify(tabs, baseName) {
  // タブが4つ未満ならサブ分類しない
  if (tabs.length < 4) {
    return [{
      name: baseName,
      tabs,
      reason: `${tabs.length}タブ`
    }];
  }

  // タイトルから共通キーワードを抽出
  const keywordMap = {};
  const COMMON_KEYWORDS = [
    'Issues', 'Pull Request', 'PR', 'README', 'Settings',
    'docs', 'blog', 'search', 'explore', 'login'
  ];

  for (const tab of tabs) {
    for (const kw of COMMON_KEYWORDS) {
      if (tab.title && tab.title.toLowerCase().includes(kw.toLowerCase())) {
        if (!keywordMap[kw]) keywordMap[kw] = [];
        keywordMap[kw].push(tab);
        break;
      }
    }
  }

  // 2タブ以上マッチするキーワードがあればサブグループ化
  const subGroups = [];
  const assignedUrls = new Set();

  for (const [kw, matchedTabs] of Object.entries(keywordMap)) {
    if (matchedTabs.length >= 2) {
      subGroups.push({
        name: `${baseName} - ${kw}`,
        tabs: matchedTabs,
        reason: `"${kw}" を含む${matchedTabs.length}タブ`
      });
      matchedTabs.forEach(t => assignedUrls.add(t.url));
    }
  }

  // サブ分類されなかったタブを基本グループに
  const remainingTabs = tabs.filter(t => !assignedUrls.has(t.url));
  if (subGroups.length === 0 || remainingTabs.length > 0) {
    subGroups.unshift({
      name: baseName,
      tabs: remainingTabs.length > 0 ? remainingTabs : tabs,
      reason: `${(remainingTabs.length > 0 ? remainingTabs : tabs).length}タブ`
    });
  }

  return subGroups.filter(g => g.tabs.length > 0);
}
```

---

### 4-5. `background.js`（Service Worker）

```javascript
/**
 * background.js - Service Worker
 * Manifest V3 対応
 *
 * 責務:
 * - Chrome起動時（onStartup）に保存済みグループのタブを自動復元する
 * - インストール/更新時（onInstalled）の初期化処理
 */

// Service WorkerではES Moduleのimportは利用可能（manifest.jsonにtype:moduleを指定済み）
import { loadData } from './js/storage.js';
import { openTabsBatch, isRestorable } from './js/tabManager.js';

// ─────────────────────────────────────────────────────────────────────────────
// イベントリスナー登録
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Chrome起動時の自動復元
 * ※ クラッシュ終了の場合はこのイベントは発火しないため、
 *    ポップアップの「手動復元」ボタンでカバーする
 */
chrome.runtime.onStartup.addListener(async () => {
  console.log('[TabGroupManager] onStartup: 自動復元を開始します');
  await restoreAllGroups('startup');
});

/**
 * 拡張機能インストール・更新時の処理
 */
chrome.runtime.onInstalled.addListener(async (details) => {
  if (details.reason === 'install') {
    console.log('[TabGroupManager] 初回インストール: 初期データを設定します');
    await initializeStorage();
  } else if (details.reason === 'update') {
    console.log(`[TabGroupManager] 更新完了: ${details.previousVersion} → ${chrome.runtime.getManifest().version}`);
  }
});

// ─────────────────────────────────────────────────────────────────────────────
// メッセージハンドラ（popup.jsからの指示を受け付ける）
// ─────────────────────────────────────────────────────────────────────────────

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === 'RESTORE_ALL_GROUPS') {
    // 非同期処理のためtrueを返してチャネルを維持する
    restoreAllGroups('manual')
      .then(result => sendResponse({ success: true, result }))
      .catch(err => sendResponse({ success: false, error: err.message }));
    return true;
  }

  if (message.type === 'RESTORE_GROUP') {
    restoreSingleGroup(message.groupId)
      .then(result => sendResponse({ success: true, result }))
      .catch(err => sendResponse({ success: false, error: err.message }));
    return true;
  }
});

// ─────────────────────────────────────────────────────────────────────────────
// 内部処理
// ─────────────────────────────────────────────────────────────────────────────

/**
 * 全グループを復元する
 * @param {'startup'|'manual'} trigger
 * @returns {Promise<{totalOpened: number, totalSkipped: number, groupCount: number}>}
 */
async function restoreAllGroups(trigger) {
  const data = await loadData();
  const { groups, settings } = data;

  // 自動復元が無効な場合はスキップ（スタートアップのみ）
  if (trigger === 'startup' && !settings.autoRestoreOnStartup) {
    console.log('[TabGroupManager] 自動復元は無効に設定されています');
    return { totalOpened: 0, totalSkipped: 0, groupCount: 0 };
  }

  const groupList = Object.values(groups).sort((a, b) => a.createdAt - b.createdAt);

  if (groupList.length === 0) {
    console.log('[TabGroupManager] 復元するグループがありません');
    return { totalOpened: 0, totalSkipped: 0, groupCount: 0 };
  }

  let totalOpened = 0;
  let totalSkipped = 0;

  for (const group of groupList) {
    if (!group.tabs || group.tabs.length === 0) continue;

    const restorableTabs = group.tabs.filter(t => isRestorable(t.url));
    const { opened, skipped } = await openTabsBatch(
      restorableTabs,
      settings.maxRestoreTabsPerGroup
    );

    totalOpened += opened;
    totalSkipped += skipped;

    console.log(`[TabGroupManager] グループ「${group.name}」: ${opened}タブ復元 / ${skipped}タブスキップ`);
  }

  console.log(`[TabGroupManager] 復元完了: 合計${totalOpened}タブ（${trigger}）`);
  return { totalOpened, totalSkipped, groupCount: groupList.length };
}

/**
 * 単一グループを復元する
 * @param {string} groupId
 * @returns {Promise<{opened: number, skipped: number}>}
 */
async function restoreSingleGroup(groupId) {
  const data = await loadData();
  const group = data.groups[groupId];

  if (!group) {
    throw new Error(`グループが見つかりません: ${groupId}`);
  }

  const restorableTabs = (group.tabs || []).filter(t => isRestorable(t.url));
  const result = await openTabsBatch(restorableTabs, data.settings.maxRestoreTabsPerGroup);

  console.log(`[TabGroupManager] グループ「${group.name}」復元: ${result.opened}タブ`);
  return result;
}

/**
 * 初回インストール時にデフォルトデータを初期化する
 */
async function initializeStorage() {
  const STORAGE_KEY = 'tabGroupManager';
  return new Promise((resolve) => {
    chrome.storage.local.get(STORAGE_KEY, (result) => {
      // 既存データがあれば上書きしない
      if (result[STORAGE_KEY]) {
        resolve();
        return;
      }
      chrome.storage.local.set({
        [STORAGE_KEY]: {
          groups: {},
          settings: {
            autoRestoreOnStartup: true,
            maxRestoreTabsPerGroup: 20
          }
        }
      }, resolve);
    });
  });
}
```

---

### 4-6. `popup/popup.html`

```html
<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>TabGroup Manager</title>
  <link rel="stylesheet" href="popup.css">
</head>
<body>

  <!-- ヘッダー -->
  <header class="app-header">
    <div class="app-title">
      <span class="app-icon">🗂</span>
      <span class="app-name">TabGroup Manager</span>
    </div>
  </header>

  <!-- アクションバー -->
  <div class="action-bar">
    <button id="btn-create-group" class="btn btn-primary">
      ＋ 新しいグループ
    </button>
    <button id="btn-auto-classify" class="btn btn-secondary">
      🔮 自動提案
    </button>
  </div>

  <!-- グループ一覧 -->
  <main id="group-list" class="group-list">
    <!-- GroupCardがJSで動的に挿入される -->
    <div id="empty-state" class="empty-state" hidden>
      <p class="empty-state__icon">📭</p>
      <p class="empty-state__text">グループがありません</p>
      <p class="empty-state__sub">「新しいグループ」から作成してください</p>
    </div>
  </main>

  <!-- フッター -->
  <footer class="app-footer">
    <button id="btn-restore-all" class="btn btn-outline btn-sm">
      ♻ 全グループを復元
    </button>
    <span id="storage-info" class="storage-info"></span>
  </footer>

  <!-- ========== モーダル: グループ作成 ========== -->
  <div id="modal-create" class="modal" hidden role="dialog" aria-modal="true" aria-labelledby="modal-create-title">
    <div class="modal__backdrop"></div>
    <div class="modal__content">
      <h2 id="modal-create-title" class="modal__title">新しいグループを作成</h2>
      <div class="form-group">
        <label for="input-group-name" class="form-label">グループ名</label>
        <input
          id="input-group-name"
          type="text"
          class="form-input"
          placeholder="例: 仕事, 調査, SNS..."
          maxlength="30"
          autocomplete="off"
        />
      </div>
      <div class="form-group">
        <label class="form-label">グループカラー</label>
        <div id="color-picker" class="color-picker">
          <!-- 色選択ボタンがJSで挿入される -->
        </div>
      </div>
      <div class="modal__actions">
        <button id="btn-create-confirm" class="btn btn-primary">作成</button>
        <button id="btn-create-cancel" class="btn btn-ghost">キャンセル</button>
      </div>
    </div>
  </div>

  <!-- ========== モーダル: グループ名編集 ========== -->
  <div id="modal-rename" class="modal" hidden role="dialog" aria-modal="true" aria-labelledby="modal-rename-title">
    <div class="modal__backdrop"></div>
    <div class="modal__content">
      <h2 id="modal-rename-title" class="modal__title">グループ名を編集</h2>
      <div class="form-group">
        <label for="input-rename" class="form-label">新しいグループ名</label>
        <input
          id="input-rename"
          type="text"
          class="form-input"
          maxlength="30"
          autocomplete="off"
        />
      </div>
      <div class="modal__actions">
        <button id="btn-rename-confirm" class="btn btn-primary">保存</button>
        <button id="btn-rename-cancel" class="btn btn-ghost">キャンセル</button>
      </div>
    </div>
  </div>

  <!-- ========== モーダル: 自動分類提案 ========== -->
  <div id="modal-classify" class="modal" hidden role="dialog" aria-modal="true" aria-labelledby="modal-classify-title">
    <div class="modal__backdrop"></div>
    <div class="modal__content modal__content--wide">
      <h2 id="modal-classify-title" class="modal__title">🔮 自動分類提案</h2>
      <p class="modal__description">現在開いているタブのドメイン・タイトルを分析した結果です。</p>
      <div id="classify-proposals" class="classify-proposals">
        <!-- 提案一覧がJSで挿入される -->
      </div>
      <div class="modal__actions">
        <button id="btn-classify-apply" class="btn btn-primary">この提案を適用</button>
        <button id="btn-classify-cancel" class="btn btn-ghost">キャンセル</button>
      </div>
    </div>
  </div>

  <!-- ========== 通知トースト ========== -->
  <div id="toast" class="toast" hidden role="alert" aria-live="polite"></div>

  <!-- ========== コンテキストメニュー（グループ操作） ========== -->
  <div id="context-menu" class="context-menu" hidden role="menu">
    <button id="menu-rename"    class="context-menu__item" role="menuitem">✏ 名前を編集</button>
    <button id="menu-open-all"  class="context-menu__item" role="menuitem">📂 全タブを開く</button>
    <button id="menu-close-all" class="context-menu__item" role="menuitem">📕 全タブを閉じる</button>
    <div class="context-menu__divider"></div>
    <button id="menu-delete"    class="context-menu__item context-menu__item--danger" role="menuitem">🗑 グループを削除</button>
  </div>

  <script src="popup.js" type="module"></script>
</body>
</html>
```

---

### 4-7. `popup/popup.css`

```css
/* ═══════════════════════════════════════════════
   CSS Custom Properties（デザイントークン）
═══════════════════════════════════════════════ */
:root {
  --color-bg:           #1a1a2e;
  --color-bg-secondary: #16213e;
  --color-bg-card:      #0f3460;
  --color-bg-hover:     #1a4a7a;
  --color-accent:       #4f8ef7;
  --color-accent-hover: #6aa3ff;
  --color-danger:       #e74c3c;
  --color-success:      #2ecc71;
  --color-warning:      #f39c12;
  --color-text:         #e0e0e0;
  --color-text-muted:   #8899aa;
  --color-border:       #2a4a6a;
  --color-shadow:       rgba(0, 0, 0, 0.4);

  --font-size-xs:    11px;
  --font-size-sm:    12px;
  --font-size-base:  13px;
  --font-size-md:    14px;
  --font-size-lg:    16px;

  --radius-sm:   4px;
  --radius-md:   8px;
  --radius-lg:   12px;

  --spacing-xs:  4px;
  --spacing-sm:  8px;
  --spacing-md:  12px;
  --spacing-lg:  16px;
  --spacing-xl:  24px;

  --transition: 0.15s ease;

  --popup-width: 380px;
}

/* ─── リセット ─── */
*, *::before, *::after {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

/* ─── ベース ─── */
html, body {
  width: var(--popup-width);
  min-height: 200px;
  max-height: 600px;
  overflow-x: hidden;
  font-family: 'Segoe UI', 'Helvetica Neue', Arial, sans-serif;
  font-size: var(--font-size-base);
  background-color: var(--color-bg);
  color: var(--color-text);
  line-height: 1.5;
}

/* ═══════════════════════════════════════════════
   ヘッダー
═══════════════════════════════════════════════ */
.app-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--spacing-md) var(--spacing-lg);
  background: var(--color-bg-secondary);
  border-bottom: 1px solid var(--color-border);
  position: sticky;
  top: 0;
  z-index: 10;
}

.app-title {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
}

.app-icon {
  font-size: 18px;
}

.app-name {
  font-size: var(--font-size-md);
  font-weight: 600;
  letter-spacing: 0.3px;
  color: var(--color-text);
}

/* ═══════════════════════════════════════════════
   アクションバー
═══════════════════════════════════════════════ */
.action-bar {
  display: flex;
  gap: var(--spacing-sm);
  padding: var(--spacing-sm) var(--spacing-lg);
  background: var(--color-bg-secondary);
  border-bottom: 1px solid var(--color-border);
}

/* ═══════════════════════════════════════════════
   ボタン
═══════════════════════════════════════════════ */
.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--spacing-xs);
  padding: 6px var(--spacing-md);
  border: none;
  border-radius: var(--radius-sm);
  font-size: var(--font-size-sm);
  font-weight: 500;
  cursor: pointer;
  transition: background-color var(--transition), opacity var(--transition);
  white-space: nowrap;
  line-height: 1.4;
}

.btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.btn-primary {
  background-color: var(--color-accent);
  color: #fff;
}

.btn-primary:hover:not(:disabled) {
  background-color: var(--color-accent-hover);
}

.btn-secondary {
  background-color: var(--color-bg-card);
  color: var(--color-text);
  border: 1px solid var(--color-border);
}

.btn-secondary:hover:not(:disabled) {
  background-color: var(--color-bg-hover);
}

.btn-outline {
  background-color: transparent;
  color: var(--color-text-muted);
  border: 1px solid var(--color-border);
}

.btn-outline:hover:not(:disabled) {
  background-color: var(--color-bg-card);
  color: var(--color-text);
}

.btn-ghost {
  background-color: transparent;
  color: var(--color-text-muted);
}

.btn-ghost:hover:not(:disabled) {
  background-color: var(--color-bg-card);
  color: var(--color-text);
}

.btn-sm {
  padding: 4px var(--spacing-sm);
  font-size: var(--font-size-xs);
}

.btn-danger {
  background-color: var(--color-danger);
  color: #fff;
}

.btn-icon {
  width: 24px;
  height: 24px;
  padding: 0;
  background: transparent;
  border: none;
  border-radius: var(--radius-sm);
  color: var(--color-text-muted);
  cursor: pointer;
  font-size: 14px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  transition: background-color var(--transition), color var(--transition);
}

.btn-icon:hover {
  background-color: var(--color-bg-hover);
  color: var(--color-text);
}

.btn-icon--danger:hover {
  background-color: rgba(231, 76, 60, 0.15);
  color: var(--color-danger);
}

/* ═══════════════════════════════════════════════
   グループリスト
═══════════════════════════════════════════════ */
.group-list {
  flex: 1;
  overflow-y: auto;
  max-height: 430px;
  padding: var(--spacing-sm) var(--spacing-sm);
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
}

.group-list::-webkit-scrollbar {
  width: 4px;
}

.group-list::-webkit-scrollbar-track {
  background: transparent;
}

.group-list::-webkit-scrollbar-thumb {
  background: var(--color-border);
  border-radius: 2px;
}

/* ─── グループカード ─── */
.group-card {
  background: var(--color-bg-card);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  overflow: hidden;
  transition: box-shadow var(--transition);
}

.group-card:hover {
  box-shadow: 0 2px 8px var(--color-shadow);
}

/* グループカラーの左ボーダー */
.group-card[data-color] {
  border-left: 3px solid var(--color-accent);
}

/* ─── グループヘッダー ─── */
.group-header {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  padding: var(--spacing-sm) var(--spacing-md);
  cursor: pointer;
  user-select: none;
}

.group-header:hover {
  background-color: var(--color-bg-hover);
}

.group-collapse-icon {
  font-size: 10px;
  color: var(--color-text-muted);
  transition: transform var(--transition);
  flex-shrink: 0;
  width: 12px;
}

.group-card.is-collapsed .group-collapse-icon {
  transform: rotate(-90deg);
}

.group-color-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.group-name {
  flex: 1;
  font-size: var(--font-size-sm);
  font-weight: 600;
  color: var(--color-text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.group-tab-count {
  font-size: var(--font-size-xs);
  color: var(--color-text-muted);
  flex-shrink: 0;
  background: var(--color-bg-secondary);
  padding: 1px 6px;
  border-radius: 10px;
}

.group-menu-btn {
  opacity: 0;
  transition: opacity var(--transition);
}

.group-header:hover .group-menu-btn {
  opacity: 1;
}

/* ─── タブリスト ─── */
.tab-list {
  padding: 0 var(--spacing-sm) var(--spacing-sm);
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.group-card.is-collapsed .tab-list {
  display: none;
}

/* ─── タブアイテム ─── */
.tab-item {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  padding: 4px var(--spacing-sm);
  border-radius: var(--radius-sm);
  transition: background-color var(--transition);
  min-height: 28px;
}

.tab-item:hover {
  background-color: var(--color-bg-hover);
}

.tab-favicon {
  width: 14px;
  height: 14px;
  flex-shrink: 0;
  border-radius: 2px;
  object-fit: contain;
}

.tab-favicon--placeholder {
  width: 14px;
  height: 14px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 10px;
  flex-shrink: 0;
}

.tab-title {
  flex: 1;
  font-size: var(--font-size-xs);
  color: var(--color-text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  cursor: pointer;
}

.tab-title:hover {
  color: var(--color-accent);
  text-decoration: underline;
}

.tab-remove-btn {
  opacity: 0;
  transition: opacity var(--transition);
  font-size: 11px;
  line-height: 1;
}

.tab-item:hover .tab-remove-btn {
  opacity: 1;
}

/* ─── タブ追加ボタン ─── */
.add-tab-btn {
  display: flex;
  align-items: center;
  gap: var(--spacing-xs);
  padding: 4px var(--spacing-sm);
  border-radius: var(--radius-sm);
  border: 1px dashed var(--color-border);
  background: transparent;
  color: var(--color-text-muted);
  font-size: var(--font-size-xs);
  cursor: pointer;
  width: 100%;
  transition: all var(--transition);
  margin-top: var(--spacing-xs);
}

.add-tab-btn:hover {
  border-color: var(--color-accent);
  color: var(--color-accent);
  background-color: rgba(79, 142, 247, 0.05);
}

/* ═══════════════════════════════════════════════
   空状態
═══════════════════════════════════════════════ */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: var(--spacing-xl);
  gap: var(--spacing-sm);
  text-align: center;
}

.empty-state__icon {
  font-size: 36px;
}

.empty-state__text {
  font-size: var(--font-size-md);
  color: var(--color-text);
  font-weight: 500;
}

.empty-state__sub {
  font-size: var(--font-size-sm);
  color: var(--color-text-muted);
}

/* ═══════════════════════════════════════════════
   フッター
═══════════════════════════════════════════════ */
.app-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--spacing-sm) var(--spacing-lg);
  border-top: 1px solid var(--color-border);
  background: var(--color-bg-secondary);
}

.storage-info {
  font-size: var(--font-size-xs);
  color: var(--color-text-muted);
}

/* ═══════════════════════════════════════════════
   モーダル
═══════════════════════════════════════════════ */
.modal {
  position: fixed;
  inset: 0;
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
}

.modal[hidden] {
  display: none;
}

.modal__backdrop {
  position: absolute;
  inset: 0;
  background: rgba(0, 0, 0, 0.6);
  backdrop-filter: blur(2px);
}

.modal__content {
  position: relative;
  z-index: 1;
  background: var(--color-bg-secondary);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  padding: var(--spacing-lg);
  width: 320px;
  max-width: calc(var(--popup-width) - 32px);
  box-shadow: 0 8px 32px var(--color-shadow);
  animation: modalIn 0.15s ease;
}

.modal__content--wide {
  width: 340px;
}

@keyframes modalIn {
  from { opacity: 0; transform: translateY(-8px) scale(0.97); }
  to   { opacity: 1; transform: translateY(0) scale(1); }
}

.modal__title {
  font-size: var(--font-size-lg);
  font-weight: 600;
  margin-bottom: var(--spacing-md);
  color: var(--color-text);
}

.modal__description {
  font-size: var(--font-size-sm);
  color: var(--color-text-muted);
  margin-bottom: var(--spacing-md);
}

.modal__actions {
  display: flex;
  gap: var(--spacing-sm);
  justify-content: flex-end;
  margin-top: var(--spacing-lg);
}

/* ─── フォーム ─── */
.form-group {
  margin-bottom: var(--spacing-md);
}

.form-label {
  display: block;
  font-size: var(--font-size-sm);
  color: var(--color-text-muted);
  margin-bottom: var(--spacing-xs);
}

.form-input {
  width: 100%;
  padding: 8px var(--spacing-md);
  background: var(--color-bg);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  color: var(--color-text);
  font-size: var(--font-size-base);
  outline: none;
  transition: border-color var(--transition);
}

.form-input:focus {
  border-color: var(--color-accent);
}

/* ─── カラーピッカー ─── */
.color-picker {
  display: flex;
  gap: var(--spacing-sm);
  flex-wrap: wrap;
}

.color-swatch {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  border: 2px solid transparent;
  cursor: pointer;
  transition: transform var(--transition), border-color var(--transition);
}

.color-swatch:hover {
  transform: scale(1.15);
}

.color-swatch.is-selected {
  border-color: #fff;
  transform: scale(1.15);
}

/* ─── 自動分類提案リスト ─── */
.classify-proposals {
  max-height: 280px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
  margin-bottom: var(--spacing-sm);
}

.classify-proposals::-webkit-scrollbar {
  width: 4px;
}

.classify-proposals::-webkit-scrollbar-thumb {
  background: var(--color-border);
  border-radius: 2px;
}

.proposal-item {
  background: var(--color-bg);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  padding: var(--spacing-sm) var(--spacing-md);
}

.proposal-item__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--spacing-xs);
}

.proposal-item__name {
  font-size: var(--font-size-sm);
  font-weight: 600;
  color: var(--color-text);
}

.proposal-item__count {
  font-size: var(--font-size-xs);
  color: var(--color-text-muted);
  background: var(--color-bg-secondary);
  padding: 1px 6px;
  border-radius: 10px;
}

.proposal-item__reason {
  font-size: var(--font-size-xs);
  color: var(--color-text-muted);
}

.proposal-item__tabs {
  margin-top: var(--spacing-xs);
  padding-left: var(--spacing-md);
  font-size: var(--font-size-xs);
  color: var(--color-text-muted);
  line-height: 1.8;
}

.proposal-item__tab {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* ═══════════════════════════════════════════════
   コンテキストメニュー
═══════════════════════════════════════════════ */
.context-menu {
  position: fixed;
  z-index: 2000;
  background: var(--color-bg-secondary);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: var(--spacing-xs);
  min-width: 160px;
  box-shadow: 0 4px 16px var(--color-shadow);
  animation: contextMenuIn 0.1s ease;
}

.context-menu[hidden] {
  display: none;
}

@keyframes contextMenuIn {
  from { opacity: 0; transform: scale(0.95); }
  to   { opacity: 1; transform: scale(1); }
}

.context-menu__item {
  display: block;
  width: 100%;
  padding: 6px var(--spacing-md);
  background: transparent;
  border: none;
  border-radius: var(--radius-sm);
  color: var(--color-text);
  font-size: var(--font-size-sm);
  text-align: left;
  cursor: pointer;
  transition: background-color var(--transition);
}

.context-menu__item:hover {
  background-color: var(--color-bg-hover);
}

.context-menu__item--danger {
  color: var(--color-danger);
}

.context-menu__item--danger:hover {
  background-color: rgba(231, 76, 60, 0.1);
}

.context-menu__divider {
  height: 1px;
  background: var(--color-border);
  margin: var(--spacing-xs) 0;
}

/* ═══════════════════════════════════════════════
   トースト通知
═══════════════════════════════════════════════ */
.toast {
  position: fixed;
  bottom: var(--spacing-lg);
  left: 50%;
  transform: translateX(-50%);
  z-index: 3000;
  background: var(--color-bg-card);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: var(--spacing-sm) var(--spacing-lg);
  font-size: var(--font-size-sm);
  color: var(--color-text);
  box-shadow: 0 4px 16px var(--color-shadow);
  animation: toastIn 0.2s ease;
  white-space: nowrap;
  max-width: calc(var(--popup-width) - 32px);
  overflow: hidden;
  text-overflow: ellipsis;
}

.toast[hidden] {
  display: none;
}

.toast--success { border-left: 3px solid var(--color-success); }
.toast--error   { border-left: 3px solid var(--color-danger); }
.toast--info    { border-left: 3px solid var(--color-accent); }

@keyframes toastIn {
  from { opacity: 0; transform: translateX(-50%) translateY(8px); }
  to   { opacity: 1; transform: translateX(-50%) translateY(0); }
}

/* ═══════════════════════════════════════════════
   ローディング状態
═══════════════════════════════════════════════ */
.loading-spinner {
  display: inline-block;
  width: 12px;
  height: 12px;
  border: 2px solid var(--color-border);
  border-top-color: var(--color-accent);
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
```

---

### 4-8. `popup/popup.js`（メインUIロジック）

```javascript
/**
 * popup.js
 * ポップアップUIのメインロジック
 * 責務: UIの生成・イベント処理・各モジュールの呼び出し
 */

import {
  getGroups,
  createGroup,
  updateGroup,
  deleteGroup,
  addTabToGroup,
  removeTabFromGroup,
  bulkCreateGroups,
  loadData
} from '../js/storage.js';

import {
  getCurrentTab,
  getAllTabs,
  openTabsBatch,
  getOpenTabUrls
} from '../js/tabManager.js';

import { classifyTabs } from '../js/classifier.js';

// ─────────────────────────────────────────────────────────────────────────────
// アプリケーション状態
// ─────────────────────────────────────────────────────────────────────────────

const AppState = {
  groups: [],             // 現在のグループ一覧
  contextMenuGroupId: '', // コンテキストメニューが対象とするグループID
  classifyProposals: [],  // 自動分類提案結果
  selectedColor: '#4f8ef7' // グループ作成時に選択中の色
};

const GROUP_COLORS = [
  '#4f8ef7', // ブルー（デフォルト）
  '#f7874f', // オレンジ
  '#4ff78e', // グリーン
  '#f74f8e', // ピンク
  '#8e4ff7', // パープル
  '#f7d44f', // イエロー
  '#4fd4f7', // シアン
  '#f74f4f'  // レッド
];

// ─────────────────────────────────────────────────────────────────────────────
// DOM参照キャッシュ
// ─────────────────────────────────────────────────────────────────────────────

const DOM = {
  groupList:          () => document.getElementById('group-list'),
  emptyState:         () => document.getElementById('empty-state'),
  toast:              () => document.getElementById('toast'),
  contextMenu:        () => document.getElementById('context-menu'),
  storageInfo:        () => document.getElementById('storage-info'),

  // ボタン
  btnCreateGroup:     () => document.getElementById('btn-create-group'),
  btnAutoClassify:    () => document.getElementById('btn-auto-classify'),
  btnRestoreAll:      () => document.getElementById('btn-restore-all'),

  // グループ作成モーダル
  modalCreate:        () => document.getElementById('modal-create'),
  inputGroupName:     () => document.getElementById('input-group-name'),
  colorPicker:        () => document.getElementById('color-picker'),
  btnCreateConfirm:   () => document.getElementById('btn-create-confirm'),
  btnCreateCancel:    () => document.getElementById('btn-create-cancel'),

  // グループ名編集モーダル
  modalRename:        () => document.getElementById('modal-rename'),
  inputRename:        () => document.getElementById('input-rename'),
  btnRenameConfirm:   () => document.getElementById('btn-rename-confirm'),
  btnRenameCancel:    () => document.getElementById('btn-rename-cancel'),

  // 自動分類モーダル
  modalClassify:      () => document.getElementById('modal-classify'),
  classifyProposals:  () => document.getElementById('classify-proposals'),
  btnClassifyApply:   () => document.getElementById('btn-classify-apply'),
  btnClassifyCancel:  () => document.getElementById('btn-classify-cancel'),

  // コンテキストメニュー
  menuRename:         () => document.getElementById('menu-rename'),
  menuOpenAll:        () => document.getElementById('menu-open-all'),
  menuCloseAll:       () => document.getElementById('menu-close-all'),
  menuDelete:         () => document.getElementById('menu-delete'),
};

// ─────────────────────────────────────────────────────────────────────────────
// 初期化
// ─────────────────────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', async () => {
  initColorPicker();
  bindGlobalEvents();
  await renderAll();
});

/**
 * カラーピッカーを初期化する
 */
function initColorPicker() {
  const picker = DOM.colorPicker();
  picker.innerHTML = '';

  GROUP_COLORS.forEach(color => {
    const swatch = document.createElement('button');
    swatch.className = `color-swatch${color === AppState.selectedColor ? ' is-selected' : ''}`;
    swatch.style.backgroundColor = color;
    swatch.setAttribute('aria-label', `色: ${color}`);
    swatch.dataset.color = color;

    swatch.addEventListener('click', () => {
      AppState.selectedColor = color;
      // 全スウォッチの選択状態をリセット
      picker.querySelectorAll('.color-swatch').forEach(s => {
        s.classList.toggle('is-selected', s.dataset.color === color);
      });
    });

    picker.appendChild(swatch);
  });
}

// ─────────────────────────────────────────────────────────────────────────────
// レンダリング
// ─────────────────────────────────────────────────────────────────────────────

/**
 * グループ一覧を再描画する
 */
async function renderAll() {
  try {
    AppState.groups = await getGroups();
    renderGroupList();
    await updateStorageInfo();
  } catch (e) {
    showToast(`データ読み込みエラー: ${e.message}`, 'error');
  }
}

/**
 * グループ一覧のHTML要素を生成してDOMに挿入する
 */
function renderGroupList() {
  const container = DOM.groupList();
  const emptyState = DOM.emptyState();

  // 既存カードを削除（emptyStateは残す）
  container.querySelectorAll('.group-card').forEach(el => el.remove());

  if (AppState.groups.length === 0) {
    emptyState.hidden = false;
    return;
  }

  emptyState.hidden = true;

  AppState.groups.forEach(group => {
    const card = createGroupCard(group);
    // emptyStateの前に挿入
    container.insertBefore(card, emptyState);
  });
}

/**
 * グループカードDOM要素を生成する
 * @param {Object} group
 * @returns {HTMLElement}
 */
function createGroupCard(group) {
  const card = document.createElement('div');
  card.className = `group-card${group.collapsed ? ' is-collapsed' : ''}`;
  card.dataset.groupId = group.id;
  card.style.borderLeftColor = group.color;

  card.innerHTML = `
    <div class="group-header" role="button" tabindex="0" aria-expanded="${!group.collapsed}">
      <span class="group-collapse-icon">▼</span>
      <span class="group-color-dot" style="background-color: ${escapeHtml(group.color)}"></span>
      <span class="group-name" title="${escapeHtml(group.name)}">${escapeHtml(group.name)}</span>
      <span class="group-tab-count">${group.tabs.length}タブ</span>
      <button class="btn-icon group-menu-btn" aria-label="グループメニュー" title="グループメニュー">⋯</button>
    </div>
    <div class="tab-list" role="list">
      ${group.tabs.map(tab => createTabItemHTML(tab)).join('')}
      <button class="add-tab-btn" aria-label="現在のタブを追加">
        ＋ 現在のタブを追加
      </button>
    </div>
  `;

  // ─── イベント: 折りたたみ ───
  const header = card.querySelector('.group-header');
  header.addEventListener('click', (e) => {
    // メニューボタンのクリックは無視
    if (e.target.closest('.group-menu-btn')) return;
    toggleGroupCollapse(group.id, card);
  });

  header.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      if (!e.target.closest('.group-menu-btn')) {
        toggleGroupCollapse(group.id, card);
      }
    }
  });

  // ─── イベント: メニューボタン ───
  const menuBtn = card.querySelector('.group-menu-btn');
  menuBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    showContextMenu(e, group.id);
  });

  // ─── イベント: タブ削除 ───
  card.querySelectorAll('.tab-remove-btn').forEach(btn => {
    btn.addEventListener('click', async (e) => {
      e.stopPropagation();
      const tabId = btn.dataset.tabId;
      await handleRemoveTab(group.id, tabId);
    });
  });

  // ─── イベント: タブタイトルクリック（URLを開く） ───
  card.querySelectorAll('.tab-title[data-url]').forEach(el => {
    el.addEventListener('click', (e) => {
      e.stopPropagation();
      chrome.tabs.create({ url: el.dataset.url, active: true });
    });
  });

  // ─── イベント: 現在のタブを追加 ───
  const addTabBtn = card.querySelector('.add-tab-btn');
  addTabBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    handleAddCurrentTab(group.id);
  });

  return card;
}

/**
 * タブアイテムのHTML文字列を生成する
 * @param {Object} tab
 * @returns {string}
 */
function createTabItemHTML(tab) {
  const faviconHTML = tab.favicon
    ? `<img class="tab-favicon" src="${escapeHtml(tab.favicon)}" alt="" onerror="this.style.display='none'">`
    : `<span class="tab-favicon--placeholder">🔗</span>`;

  return `
    <div class="tab-item" role="listitem">
      ${faviconHTML}
      <span
        class="tab-title"
        data-url="${escapeHtml(tab.url)}"
        title="${escapeHtml(tab.url)}"
      >${escapeHtml(tab.title)}</span>
      <button
        class="btn-icon btn-icon--danger tab-remove-btn"
        data-tab-id="${escapeHtml(tab.id)}"
        aria-label="タブを削除"
        title="グループから削除"
      >×</button>
    </div>
  `;
}

/**
 * ストレージ使用量を更新して表示する
 */
async function updateStorageInfo() {
  return new Promise((resolve) => {
    chrome.storage.local.getBytesInUse(null, (bytes) => {
      const kb = (bytes / 1024).toFixed(1);
      const maxKb = (5 * 1024).toFixed(0); // 5MB = 5120KB
      DOM.storageInfo().textContent = `ストレージ: ${kb}KB / ${maxKb}KB`;
      resolve();
    });
  });
}

// ─────────────────────────────────────────────────────────────────────────────
// イベントハンドラ
// ─────────────────────────────────────────────────────────────────────────────

/**
 * グローバルイベントを登録する
 */
function bindGlobalEvents() {

  // ── グループ作成ボタン ──
  DOM.btnCreateGroup().addEventListener('click', () => {
    openModal(DOM.modalCreate());
    DOM.inputGroupName().value = '';
    DOM.inputGroupName().focus();
  });

  DOM.btnCreateConfirm().addEventListener('click', handleCreateGroup);
  DOM.btnCreateCancel().addEventListener('click', () => closeModal(DOM.modalCreate()));

  DOM.inputGroupName().addEventListener('keydown', (e) => {
    if (e.key === 'Enter') handleCreateGroup();
    if (e.key === 'Escape') closeModal(DOM.modalCreate());
  });

  // ── グループ名編集 ──
  DOM.btnRenameConfirm().addEventListener('click', handleRenameGroup);
  DOM.btnRenameCancel().addEventListener('click', () => closeModal(DOM.modalRename()));

  DOM.inputRename().addEventListener('keydown', (e) => {
    if (e.key === 'Enter') handleRenameGroup();
    if (e.key === 'Escape') closeModal(DOM.modalRename());
  });

  // ── 自動分類 ──
  DOM.btnAutoClassify().addEventListener('click', handleAutoClassify);
  DOM.btnClassifyApply().addEventListener('click', handleApplyClassify);
  DOM.btnClassifyCancel().addEventListener('click', () => closeModal(DOM.modalClassify()));

  // ── 全グループ復元 ──
  DOM.btnRestoreAll().addEventListener('click', handleRestoreAll);

  // ── コンテキストメニュー ──
  DOM.menuRename().addEventListener('click', () => {
    closeContextMenu();
    openRenameModal(AppState.contextMenuGroupId);
  });

  DOM.menuOpenAll().addEventListener('click', () => {
    closeContextMenu();
    handleOpenAllTabs(AppState.contextMenuGroupId);
  });

  DOM.menuCloseAll().addEventListener('click', () => {
    closeContextMenu();
    handleCloseAllSavedTabs(AppState.contextMenuGroupId);
  });

  DOM.menuDelete().addEventListener('click', () => {
    closeContextMenu();
    handleDeleteGroup(AppState.contextMenuGroupId);
  });

  // ── モーダル背景クリックで閉じる ──
  [DOM.modalCreate(), DOM.modalRename(), DOM.modalClassify()].forEach(modal => {
    modal.querySelector('.modal__backdrop').addEventListener('click', () => closeModal(modal));
  });

  // ── グローバルクリックでコンテキストメニューを閉じる ──
  document.addEventListener('click', (e) => {
    if (!e.target.closest('.context-menu')) {
      closeContextMenu();
    }
  });

  // ── Escapeキーで全モーダルを閉じる ──
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      closeModal(DOM.modalCreate());
      closeModal(DOM.modalRename());
      closeModal(DOM.modalClassify());
      closeContextMenu();
    }
  });
}

// ─── グループ作成 ───

async function handleCreateGroup() {
  const name = DOM.inputGroupName().value.trim();
  if (!name) {
    DOM.inputGroupName().focus();
    showToast('グループ名を入力してください', 'error');
    return;
  }

  try {
    DOM.btnCreateConfirm().disabled = true;
    await createGroup(name, AppState.selectedColor);
    closeModal(DOM.modalCreate());
    await renderAll();
    showToast(`グループ「${name}」を作成しました`, 'success');
  } catch (e) {
    showToast(`作成エラー: ${e.message}`, 'error');
  } finally {
    DOM.btnCreateConfirm().disabled = false;
  }
}

// ─── グループ折りたたみ ───

async function toggleGroupCollapse(groupId, cardElement) {
  const isCollapsed = cardElement.classList.toggle('is-collapsed');
  const header = cardElement.querySelector('.group-header');
  header.setAttribute('aria-expanded', String(!isCollapsed));

  try {
    await updateGroup(groupId, { collapsed: isCollapsed });
  } catch (e) {
    console.warn('折りたたみ状態の保存に失敗:', e);
  }
}

// ─── タブ追加 ───

async function handleAddCurrentTab(groupId) {
  try {
    const tabInfo = await getCurrentTab();

    if (!tabInfo.url || tabInfo.url.startsWith('chrome://')) {
      showToast('このタブは追加できません（chrome://ページ）', 'error');
      return;
    }

    await addTabToGroup(groupId, tabInfo);
    await renderAll();
    showToast(`「${tabInfo.title}」をグループに追加しました`, 'success');
  } catch (e) {
    showToast(e.message, 'error');
  }
}

// ─── タブ削除 ───

async function handleRemoveTab(groupId, tabId) {
  try {
    await removeTabFromGroup(groupId, tabId);
    await renderAll();
    showToast('タブをグループから削除しました', 'info');
  } catch (e) {
    showToast(`削除エラー: ${e.message}`, 'error');
  }
}

// ─── グループ名編集 ───

function openRenameModal(groupId) {
  const group = AppState.groups.find(g => g.id === groupId);
  if (!group) return;

  DOM.inputRename().value = group.name;
  DOM.modalRename().dataset.groupId = groupId;
  openModal(DOM.modalRename());
  DOM.inputRename().select();
}

async function handleRenameGroup() {
  const groupId = DOM.modalRename().dataset.groupId;
  const newName = DOM.inputRename().value.trim();

  if (!newName) {
    DOM.inputRename().focus();
    showToast('グループ名を入力してください', 'error');
    return;
  }

  try {
    DOM.btnRenameConfirm().disabled = true;
    await updateGroup(groupId, { name: newName });
    closeModal(DOM.modalRename());
    await renderAll();
    showToast(`グループ名を「${newName}」に変更しました`, 'success');
  } catch (e) {
    showToast(`変更エラー: ${e.message}`, 'error');
  } finally {
    DOM.btnRenameConfirm().disabled = false;
  }
}

// ─── グループ削除 ───

async function handleDeleteGroup(groupId) {
  const group = AppState.groups.find(g => g.id === groupId);
  if (!group) return;

  // 確認ダイアログ（シンプルなconfirmで代替）
  const confirmed = window.confirm(
    `グループ「${group.name}」を削除しますか？\nタブのURLは消えますが、ブラウザで開いているタブには影響しません。`
  );
  if (!confirmed) return;

  try {
    await deleteGroup(groupId);
    await renderAll();
    showToast(`グループ「${group.name}」を削除しました`, 'info');
  } catch (e) {
    showToast(`削除エラー: ${e.message}`, 'error');
  }
}

// ─── 全タブを開く ───

async function handleOpenAllTabs(groupId) {
  const group = AppState.groups.find(g => g.id === groupId);
  if (!group || !group.tabs.length) {
    showToast('このグループにはタブがありません', 'info');
    return;
  }

  try {
    showToast('タブを開いています...', 'info');
    const { opened, skipped } = await openTabsBatch(group.tabs, 20);
    const msg = skipped > 0
      ? `${opened}タブを開きました（${skipped}タブは上限のためスキップ）`
      : `${opened}タブを開きました`;
    showToast(msg, 'success');
  } catch (e) {
    showToast(`エラー: ${e.message}`, 'error');
  }
}

// ─── 保存済みタブを閉じる（URLマッチング） ───

async function handleCloseAllSavedTabs(groupId) {
  const group = AppState.groups.find(g => g.id === groupId);
  if (!group || !group.tabs.length) {
    showToast('このグループにはタブがありません', 'info');
    return;
  }

  try {
    // 現在開いているタブを取得
    const openTabs = await new Promise((resolve) => {
      chrome.tabs.query({ currentWindow: true }, resolve);
    });

    // グループのURLと一致するタブIDを収集
    const groupUrls = new Set(group.tabs.map(t => t.url));
    const tabIdsToClose = openTabs
      .filter(t => t.url && groupUrls.has(t.url))
      .map(t => t.id);

    if (tabIdsToClose.length === 0) {
      showToast('現在開いているタブと一致するものがありません', 'info');
      return;
    }

    await new Promise((resolve, reject) => {
      chrome.tabs.remove(tabIdsToClose, () => {
        if (chrome.runtime.lastError) reject(new Error(chrome.runtime.lastError.message));
        else resolve();
      });
    });

    showToast(`${tabIdsToClose.length}タブを閉じました`, 'success');
  } catch (e) {
    showToast(`エラー: ${e.message}`, 'error');
  }
}

// ─── 全グループ復元 ───

async function handleRestoreAll() {
  const btn = DOM.btnRestoreAll();
  btn.disabled = true;
  btn.innerHTML = '<span class="loading-spinner"></span> 復元中...';

  try {
    const response = await new Promise((resolve, reject) => {
      chrome.runtime.sendMessage({ type: 'RESTORE_ALL_GROUPS' }, (res) => {
        if (chrome.runtime.lastError) reject(new Error(chrome.runtime.lastError.message));
        else resolve(res);
      });
    });

    if (response.success) {
      const { totalOpened, groupCount } = response.result;
      showToast(
        totalOpened > 0
          ? `${groupCount}グループ / ${totalOpened}タブを復元しました`
          : '復元するタブがありませんでした',
        'success'
      );
    } else {
      showToast(`復元エラー: ${response.error}`, 'error');
    }
  } catch (e) {
    showToast(`復元エラー: ${e.message}`, 'error');
  } finally {
    btn.disabled = false;
    btn.innerHTML = '♻ 全グループを復元';
  }
}

// ─── 自動分類提案 ───

async function handleAutoClassify() {
  const btn = DOM.btnAutoClassify();
  btn.disabled = true;
  btn.innerHTML = '<span class="loading-spinner"></span> 分析中...';

  try {
    const tabs = await getAllTabs();

    if (tabs.length === 0) {
      showToast('開いているタブが見つかりません', 'info');
      return;
    }

    const proposals = classifyTabs(tabs);
    AppState.classifyProposals = proposals;

    renderClassifyProposals(proposals);
    openModal(DOM.modalClassify());
  } catch (e) {
    showToast(`分析エラー: ${e.message}`, 'error');
  } finally {
    btn.disabled = false;
    btn.innerHTML = '🔮 自動提案';
  }
}

/**
 * 自動分類提案をモーダル内にレンダリングする
 * @param {Array} proposals
 */
function renderClassifyProposals(proposals) {
  const container = DOM.classifyProposals();
  container.innerHTML = '';

  if (proposals.length === 0) {
    container.innerHTML = '<p style="color: var(--color-text-muted); font-size: 12px;">分類できるタブが見つかりませんでした。</p>';
    return;
  }

  proposals.forEach(proposal => {
    const item = document.createElement('div');
    item.className = 'proposal-item';

    const tabListHTML = proposal.tabs.slice(0, 3).map(t =>
      `<div class="proposal-item__tab">🔗 ${escapeHtml(t.title || t.url)}</div>`
    ).join('');

    const moreCount = proposal.tabs.length - 3;

    item.innerHTML = `
      <div class="proposal-item__header">
        <span class="proposal-item__name">📁 ${escapeHtml(proposal.name)}</span>
        <span class="proposal-item__count">${proposal.tabs.length}タブ</span>
      </div>
      <div class="proposal-item__reason">${escapeHtml(proposal.reason)}</div>
      <div class="proposal-item__tabs">
        ${tabListHTML}
        ${moreCount > 0 ? `<div class="proposal-item__tab">... 他${moreCount}件</div>` : ''}
      </div>
    `;

    container.appendChild(item);
  });
}

/**
 * 自動分類提案を適用する
 */
async function handleApplyClassify() {
  if (!AppState.classifyProposals.length) return;

  const btn = DOM.btnClassifyApply();
  btn.disabled = true;
  btn.textContent = '適用中...';

  try {
    await bulkCreateGroups(AppState.classifyProposals);
    closeModal(DOM.modalClassify());
    await renderAll();
    showToast(`${AppState.classifyProposals.length}グループを作成しました`, 'success');
    AppState.classifyProposals = [];
  } catch (e) {
    showToast(`適用エラー: ${e.message}`, 'error');
  } finally {
    btn.disabled = false;
    btn.textContent = 'この提案を適用';
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// コンテキストメニュー
// ─────────────────────────────────────────────────────────────────────────────

/**
 * コンテキストメニューを表示する
 * @param {MouseEvent} e
 * @param {string} groupId
 */
function showContextMenu(e, groupId) {
  AppState.contextMenuGroupId = groupId;
  const menu = DOM.contextMenu();
  menu.hidden = false;

  // ポップアップの境界内に収まるよう位置調整
  const menuWidth = 170;
  const menuHeight = 140;
  const popupWidth = 380;
  const popupHeight = 600;

  let x = e.clientX;
  let y = e.clientY;

  if (x + menuWidth > popupWidth) x = popupWidth - menuWidth - 8;
  if (y + menuHeight > popupHeight) y = popupHeight - menuHeight - 8;

  menu.style.left = `${x}px`;
  menu.style.top = `${y}px`;
}

function closeContextMenu() {
  DOM.contextMenu().hidden = true;
  AppState.contextMenuGroupId = '';
}

// ─────────────────────────────────────────────────────────────────────────────
// モーダル
// ─────────────────────────────────────────────────────────────────────────────

function openModal(modalEl) {
  modalEl.hidden = false;
}

function closeModal(modalEl) {
  modalEl.hidden = true;
}

// ─────────────────────────────────────────────────────────────────────────────
// トースト通知
// ─────────────────────────────────────────────────────────────────────────────

let toastTimer = null;

/**
 * トースト通知を表示する
 * @param {string} message
 * @param {'success'|'error'|'info'} type
 * @param {number} [duration=2500] - 表示時間（ms）
 */
function showToast(message, type = 'info', duration = 2500) {
  const toast = DOM.toast();
  toast.textContent = message;
  toast.className = `toast toast--${type}`;
  toast.hidden = false;

  if (toastTimer) clearTimeout(toastTimer);
  toastTimer = setTimeout(() => {
    toast.hidden = true;
  }, duration);
}

// ─────────────────────────────────────────────────────────────────────────────
// ユーティリティ
// ─────────────────────────────────────────────────────────────────────────────

/**
 * XSS対策: HTMLエスケープ
 * @param {string} str
 * @returns {string}
 */
function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}
```

---

## 5. コード解説

### 5-1. アーキテクチャ全体像

```
┌─────────────────────────────────────────────────────────┐
│                    Chrome Extension                      │
│                                                         │
│  ┌──────────────────┐       ┌──────────────────────┐   │
│  │   popup.html/js   │◄────►│   background.js      │   │
│  │  （UIレイヤー）    │      │  （Service Worker）   │   │
│  └────────┬─────────┘       └──────────┬───────────┘   │
│           │                            │               │
│           ▼                            ▼               │
│  ┌──────────────────────────────────────────────────┐  │
│  │                  js/ モジュール群                  │  │
│  │  ┌──────────┐  ┌────────────┐  ┌─────────────┐  │  │
│  │  │storage.js│  │tabManager.js│  │classifier.js│  │  │
│  │  └────┬─────┘  └──────┬─────┘  └──────┬──────┘  │  │
│  └───────┼───────────────┼───────────────┼──────────┘  │
│          ▼               ▼               ▼             │
│  ┌───────────────┐  ┌──────────┐                        │
│  │chrome.storage │  │chrome.tabs│                        │
│  │    .local     │  │   API    │                        │
│  └───────────────┘  └──────────┘                        │
└─────────────────────────────────────────────────────────┘
```

### 5-2. データスキーマ詳解

```javascript
// chrome.storage.local に保存される実際のJSONイメージ
{
  "tabGroupManager": {
    "groups": {
      "ld8f2k3-abc1234": {           // generateId()が生成するUUID
        "id": "ld8f2k3-abc1234",
        "name": "仕事",
        "color": "#4f8ef7",
        "collapsed": false,          // UIの折りたたみ状態を永続化
        "createdAt": 1704067200000,  // ソート用タイムスタンプ
        "tabs": [
          {
            "id": "ld8f2k4-def5678",  // タブ個別ID（Chrome tabIdとは独立）
            "url": "https://github.com/...",
            "title": "Pull Request · GitHub",
            "favicon": "https://github.com/favicon.ico",
            "addedAt": 1704067260000
          }
        ]
      }
    },
    "settings": {
      "autoRestoreOnStartup": true,
      "maxRestoreTabsPerGroup": 20
    }
  }
}
```

**設計の意図:**
- **Chromeのtab.idを使わない理由**: Chrome再起動後はIDが変わるため、URLを識別子として使用
- **独自のタブIDを持つ理由**: 同一URLのタブが複数存在する将来の拡張に対応
- **collapsed状態を永続化する理由**: ポップアップを閉じても折りたたみ状態が保持されUXが向上する

---

### 5-3. モジュール設計の説明

#### `storage.js` の責務分離

```javascript
// ❌ 悪い例（ビジネスロジックとストレージが混在）
async function addTab(groupId, tabInfo) {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  const data = await chrome.storage.local.get('tabGroupManager');
  // ...ストレージ処理とタブ取得が混在...
}

// ✅ 良い例（本実装の方針）
// tabManager.js → タブ取得
// storage.js → データ永続化
// popup.js → 両者を組み合わせてUIに反映
async function handleAddCurrentTab(groupId) {
  const tabInfo = await getCurrentTab();     // tabManager.js
  await addTabToGroup(groupId, tabInfo);     // storage.js
  await renderAll();                         // UIの更新
}
```

---

#### `background.js` の Service Worker 制限への対応

```javascript
// Manifest V3のService Workerは非アクティブ時に終了する
// → 常駐前提の処理（setInterval等）は絶対NG

// ✅ 本実装の方針: イベントドリブンのみ
chrome.runtime.onStartup.addListener(async () => {
  // Chrome起動時の一発処理のみ → Service Worker終了しても問題なし
  await restoreAllGroups('startup');
});

// ✅ popup.js からの指示にも対応（手動復元）
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === 'RESTORE_ALL_GROUPS') {
    restoreAllGroups('manual')
      .then(result => sendResponse({ success: true, result }))
      .catch(err => sendResponse({ success: false, error: err.message }));
    return true; // ← 非同期sendResponseのためtrueを返すことが必須
  }
});
```

---

#### `classifier.js` の分類アルゴリズムフロー

```
入力タブ配列
    │
    ▼
[1] ドメイン抽出 (extractDomain)
    │  "https://github.com/user/repo" → "github.com"
    │  "https://www.google.com/..."   → "google.com"
    ▼
[2] ドメイン単位でグルーピング (groupByDomain)
    │  { "github.com": [tab1, tab2, tab3], "google.com": [tab4] }
    ▼
[3] タブ数でフィルタリング
    │  ≥2タブ → 独立グループ候補
    │  1タブ  → 「その他」グループに集約
    ▼
[4] 人間可読名に変換 (domainToGroupName)
    │  "github.com" → "GitHub"
    │  "notion.so"  → "Notion"
    ▼
[5] サブ分類の試み (trySubClassify)
    │  4タブ以上 & タイトルキーワードマッチで分割
    │  例: "GitHub - Issues" / "GitHub - Pull Request"
    ▼
[6] タブ数降順ソート
    ▼
出力: [{ name, tabs, reason }]
```

---

#### XSS対策の実装

```javascript
// ユーザー入力（グループ名）や外部データ（タブタイトル）を
// innerHTML に挿入する際は必ずエスケープを適用

// ❌ 危険な例
card.innerHTML = `<span>${group.name}</span>`; // XSSリスク

// ✅ 本実装（escapeHtml関数でサニタイズ）
card.innerHTML = `<span>${escapeHtml(group.name)}</span>`;

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}
```

---

### 5-4. インストール手順

```
1. tab-group-manager/ フォルダを任意の場所に作成
2. 全ファイルを配置（コードをコピー）
3. アイコン画像を icons/ に配置（PNG形式: 16x16, 48x48, 128x128）
4. Chromeで chrome://extensions/ を開く
5. 右上の「デベロッパーモード」をONにする
6. 「パッケージ化されていない拡張機能を読み込む」をクリック
7. tab-group-manager/ フォルダを選択
8. ツールバーの拡張機能アイコンをクリックして動作確認
```

---

### 5-5. 受け入れ条件との対応表

| 受け入れ条件 | 対応実装 |
|---|---|
| グループ新規作成・命名 | `handleCreateGroup()` / `createGroup()` |
| タブをグループに追加 | `handleAddCurrentTab()` / `addTabToGroup()` |
| グループからタブを削除 | `handleRemoveTab()` / `removeTabFromGroup()` |
| グループ名を編集 | `handleRenameGroup()` / `updateGroup()` |
| グループを削除 | `handleDeleteGroup()` / `deleteGroup()` |
| 自動分類提案ボタン | `handleAutoClassify()` / `classifyTabs()` |
| 再起動後の自動復元 | `chrome.runtime.onStartup` / `restoreAllGroups()` |

---

### 5-6. 今後の拡張ポイント

```javascript
// 1. グループのドラッグ&ドロップ並べ替え
//    → HTML5 Drag and Drop API または SortableJS を追加

// 2. タブのインポート/エクスポート (JSON)
//    → loadData() / saveData() を直接利用可能

// 3. 検索機能
//    → AppState.groups をフィルタリングして renderGroupList() を呼ぶだけ

// 4. chrome.storage.sync への移行（デバイス間同期）
//    → storage.js の chrome.storage.local を .sync に変更するだけで対応可
//      （容量制限100KBに注意）

// 5. タブのピン留め
//    → chrome.tabs.update(tabId, { pinned: true }) を追加
```

---

## ⚙️ バックエンド実装・設計
# Chrome拡張機能「Tab Group Manager」実装コード

## 実装概要・アーキテクチャ

```
tab-group-manager/
├── manifest.json          # 拡張機能設定（MV3）
├── background.js          # Service Worker（起動時復元）
├── popup/
│   ├── popup.html         # ポップアップUI
│   ├── popup.js           # ポップアップロジック
│   └── popup.css          # スタイル
├── js/
│   ├── storage.js         # ストレージ操作モジュール
│   ├── tabManager.js      # タブ操作モジュール
│   └── classifier.js      # 自動分類提案モジュール
└── icons/
    └── icon48.png         # アイコン（任意）
```

---

## ① manifest.json

```json
{
  "manifest_version": 3,
  "name": "Tab Group Manager",
  "version": "1.0.0",
  "description": "タブをユーザー定義グループで管理し、再起動後も自動復元するChrome拡張機能",

  "permissions": [
    "tabs",
    "storage"
  ],

  "background": {
    "service_worker": "background.js"
  },

  "action": {
    "default_popup": "popup/popup.html",
    "default_title": "Tab Group Manager"
  },

  "icons": {
    "48": "icons/icon48.png"
  }
}
```

### 解説
| フィールド | 理由 |
|---|---|
| `manifest_version: 3` | Chrome現行標準。V2は廃止予定のため |
| `permissions: tabs` | タブのURL・タイトル取得と操作に必須 |
| `permissions: storage` | `chrome.storage.local`使用に必須 |
| `service_worker` | MV3では`background.scripts`非推奨。SW形式を採用 |
| `webNavigation`等は除外 | 最小権限原則。不要なパーミッション要求をしない |

---

## ② データ設計（chrome.storage.local スキーマ）

```js
// ======================================================
// js/storage.js
// chrome.storage.local の読み書きを一元管理するモジュール
// ======================================================

/**
 * ストレージスキーマ定義（JSDocによる型定義）
 *
 * chrome.storage.local に保存されるデータ構造:
 *
 * {
 *   "groups": {
 *     "<groupId: string(UUID)>": {
 *       "id":        string,   // UUID (例: "g-1690000000000-abc123")
 *       "name":      string,   // グループ名 (例: "仕事")
 *       "color":     string,   // UIアクセント色 (例: "#4A90D9")
 *       "createdAt": number,   // 作成日時 Unix timestamp (ms)
 *       "tabs": [
 *         {
 *           "id":      string, // タブ識別子 UUID (例: "t-1690000000001-xyz")
 *           "url":     string, // タブURL
 *           "title":   string, // タブタイトル
 *           "favicon": string, // favicon URL (chrome取得)
 *           "addedAt": number  // 追加日時 Unix timestamp (ms)
 *         }
 *       ],
 *       "restoreEnabled": boolean // 再起動時に自動復元するか
 *     }
 *   }
 * }
 *
 * 設計ポイント:
 * - groups をオブジェクト(Map)形式にすることで groupId による O(1) アクセスを実現
 * - タブはグループ内に配列として埋め込み（最大100タブ想定、正規化不要）
 * - タブにも独自IDを付与し、配列インデックスに依存しない安全な削除操作を実現
 */

const StorageKeys = {
  GROUPS: "groups",
};

/**
 * グループID生成
 * @returns {string}
 */
function generateGroupId() {
  return `g-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

/**
 * タブID生成
 * @returns {string}
 */
function generateTabId() {
  return `t-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

/**
 * 全グループを取得する
 * @returns {Promise<Object>} グループマップ { groupId: groupObject }
 */
async function getAllGroups() {
  return new Promise((resolve, reject) => {
    chrome.storage.local.get(StorageKeys.GROUPS, (result) => {
      if (chrome.runtime.lastError) {
        reject(new Error(chrome.runtime.lastError.message));
        return;
      }
      // 初回アクセス時はデフォルト空オブジェクトを返す
      resolve(result[StorageKeys.GROUPS] ?? {});
    });
  });
}

/**
 * 全グループを保存する（完全上書き）
 * @param {Object} groups - グループマップ
 * @returns {Promise<void>}
 */
async function saveAllGroups(groups) {
  return new Promise((resolve, reject) => {
    chrome.storage.local.set({ [StorageKeys.GROUPS]: groups }, () => {
      if (chrome.runtime.lastError) {
        reject(new Error(chrome.runtime.lastError.message));
        return;
      }
      resolve();
    });
  });
}

/**
 * 新しいグループを作成して保存する
 * @param {string} name - グループ名
 * @param {string} [color="#4A90D9"] - アクセント色
 * @returns {Promise<Object>} 作成されたグループオブジェクト
 */
async function createGroup(name, color = "#4A90D9") {
  const groups = await getAllGroups();

  const newGroup = {
    id: generateGroupId(),
    name: name.trim(),
    color,
    createdAt: Date.now(),
    tabs: [],
    restoreEnabled: true,
  };

  groups[newGroup.id] = newGroup;
  await saveAllGroups(groups);

  return newGroup;
}

/**
 * グループ名を更新する
 * @param {string} groupId
 * @param {string} newName
 * @returns {Promise<void>}
 */
async function updateGroupName(groupId, newName) {
  const groups = await getAllGroups();

  if (!groups[groupId]) {
    throw new Error(`Group not found: ${groupId}`);
  }

  groups[groupId].name = newName.trim();
  await saveAllGroups(groups);
}

/**
 * グループを削除する
 * @param {string} groupId
 * @returns {Promise<void>}
 */
async function deleteGroup(groupId) {
  const groups = await getAllGroups();
  delete groups[groupId];
  await saveAllGroups(groups);
}

/**
 * タブをグループに追加する
 * @param {string} groupId
 * @param {{ url: string, title: string, favicon: string }} tabInfo
 * @returns {Promise<Object>} 追加されたタブオブジェクト
 */
async function addTabToGroup(groupId, tabInfo) {
  const groups = await getAllGroups();

  if (!groups[groupId]) {
    throw new Error(`Group not found: ${groupId}`);
  }

  // 同一URLの重複チェック（同じURLは同じグループに2度登録しない）
  const alreadyExists = groups[groupId].tabs.some(
    (t) => t.url === tabInfo.url
  );
  if (alreadyExists) {
    throw new Error(`Tab URL already exists in this group: ${tabInfo.url}`);
  }

  const newTab = {
    id: generateTabId(),
    url: tabInfo.url,
    title: tabInfo.title || tabInfo.url,
    favicon: tabInfo.favicon || "",
    addedAt: Date.now(),
  };

  groups[groupId].tabs.push(newTab);
  await saveAllGroups(groups);

  return newTab;
}

/**
 * タブをグループから削除する
 * @param {string} groupId
 * @param {string} tabId - StorageタブID（chrome.tabs.Tab.idではない）
 * @returns {Promise<void>}
 */
async function removeTabFromGroup(groupId, tabId) {
  const groups = await getAllGroups();

  if (!groups[groupId]) {
    throw new Error(`Group not found: ${groupId}`);
  }

  groups[groupId].tabs = groups[groupId].tabs.filter((t) => t.id !== tabId);
  await saveAllGroups(groups);
}

/**
 * グループのrestoreEnabledフラグを更新する
 * @param {string} groupId
 * @param {boolean} enabled
 * @returns {Promise<void>}
 */
async function updateRestoreEnabled(groupId, enabled) {
  const groups = await getAllGroups();

  if (!groups[groupId]) {
    throw new Error(`Group not found: ${groupId}`);
  }

  groups[groupId].restoreEnabled = enabled;
  await saveAllGroups(groups);
}

// モジュールエクスポート（popup.js / background.js から利用）
// Chrome拡張機能では ES Module の importmap が制限されるため
// グローバル名前空間にアタッチする方式を採用
window.StorageModule = {
  generateGroupId,
  generateTabId,
  getAllGroups,
  saveAllGroups,
  createGroup,
  updateGroupName,
  deleteGroup,
  addTabToGroup,
  removeTabFromGroup,
  updateRestoreEnabled,
};
```

---

## ③ タブ操作モジュール

```js
// ======================================================
// js/tabManager.js
// chrome.tabs API を使ったタブ操作の抽象化モジュール
// ======================================================

/**
 * 現在のウィンドウで開いているすべてのタブ情報を取得する
 * @returns {Promise<Array>} chrome.tabs.Tab の配列
 */
async function getCurrentWindowTabs() {
  return new Promise((resolve, reject) => {
    chrome.tabs.query({ currentWindow: true }, (tabs) => {
      if (chrome.runtime.lastError) {
        reject(new Error(chrome.runtime.lastError.message));
        return;
      }
      resolve(tabs);
    });
  });
}

/**
 * 現在アクティブなタブを取得する
 * @returns {Promise<chrome.tabs.Tab>}
 */
async function getActiveTab() {
  return new Promise((resolve, reject) => {
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      if (chrome.runtime.lastError) {
        reject(new Error(chrome.runtime.lastError.message));
        return;
      }
      if (!tabs || tabs.length === 0) {
        reject(new Error("Active tab not found"));
        return;
      }
      resolve(tabs[0]);
    });
  });
}

/**
 * chrome.tabs.Tab オブジェクトをストレージ用タブ情報に変換する
 * @param {chrome.tabs.Tab} chromeTab
 * @returns {{ url: string, title: string, favicon: string }}
 */
function chromeTabToTabInfo(chromeTab) {
  return {
    // chrome拡張機能内ページ（chrome://newtab等）はURLが取得できない場合がある
    url: chromeTab.url || chromeTab.pendingUrl || "",
    title: chromeTab.title || "",
    favicon: chromeTab.favIconUrl || "",
  };
}

/**
 * 保存済みタブのURLリストを新しいウィンドウで一括復元する
 * @param {Array<{url: string, title: string}>} savedTabs
 * @param {boolean} [newWindow=false] - trueなら新規ウィンドウで開く
 * @returns {Promise<void>}
 */
async function restoreTabs(savedTabs, newWindow = false) {
  if (!savedTabs || savedTabs.length === 0) return;

  // chrome://〜 や空URLは復元不可のためフィルタ
  const restorableUrls = savedTabs
    .map((t) => t.url)
    .filter(
      (url) =>
        url &&
        !url.startsWith("chrome://") &&
        !url.startsWith("chrome-extension://") &&
        !url.startsWith("about:")
    );

  if (restorableUrls.length === 0) return;

  if (newWindow) {
    // 新規ウィンドウで最初のタブを開き、残りをそのウィンドウに追加
    const win = await new Promise((resolve) => {
      chrome.windows.create({ url: restorableUrls[0] }, resolve);
    });

    for (const url of restorableUrls.slice(1)) {
      await new Promise((resolve) => {
        chrome.tabs.create({ url, windowId: win.id }, resolve);
      });
    }
  } else {
    // 現在のウィンドウに追加
    for (const url of restorableUrls) {
      await new Promise((resolve) => {
        chrome.tabs.create({ url, active: false }, resolve);
      });
    }
  }
}

/**
 * 指定グループのタブを現在のウィンドウで一括オープンする（ポップアップから呼び出し）
 * @param {Array<{url: string}>} savedTabs
 * @returns {Promise<void>}
 */
async function openGroupTabs(savedTabs) {
  await restoreTabs(savedTabs, false);
}

window.TabManagerModule = {
  getCurrentWindowTabs,
  getActiveTab,
  chromeTabToTabInfo,
  restoreTabs,
  openGroupTabs,
};
```

---

## ④ 自動分類提案モジュール

```js
// ======================================================
// js/classifier.js
// URLドメイン・タイトルキーワードを元にタブを自動分類提案するモジュール
// ======================================================

/**
 * URLからドメイン名（eTLD+1）を抽出する
 * @param {string} url
 * @returns {string} ドメイン名 (例: "github.com") / 取得失敗時は空文字
 */
function extractDomain(url) {
  try {
    const { hostname } = new URL(url);
    // "www." プレフィックスを除去して正規化
    return hostname.replace(/^www\./, "");
  } catch {
    return "";
  }
}

/**
 * タイトルからカテゴリキーワードを判定するルールセット
 * 順序依存（先にマッチしたルールが優先）
 *
 * @type {Array<{name: string, keywords: string[], domains: string[]}>}
 */
const CATEGORY_RULES = [
  {
    name: "開発・技術",
    keywords: [
      "github", "stackoverflow", "qiita", "zenn", "mdn", "npm",
      "docs", "documentation", "api", "reference", "tutorial",
    ],
    domains: [
      "github.com", "stackoverflow.com", "qiita.com", "zenn.dev",
      "developer.mozilla.org", "npmjs.com", "dev.to",
    ],
  },
  {
    name: "動画・エンタメ",
    keywords: ["youtube", "video", "watch", "movie", "anime", "ニコニコ"],
    domains: [
      "youtube.com", "nicovideo.jp", "netflix.com", "abema.tv",
      "twitch.tv", "tver.jp",
    ],
  },
  {
    name: "SNS・コミュニティ",
    keywords: ["twitter", "x.com", "facebook", "instagram", "reddit", "discord"],
    domains: [
      "twitter.com", "x.com", "facebook.com", "instagram.com",
      "reddit.com", "discord.com",
    ],
  },
  {
    name: "ショッピング",
    keywords: ["amazon", "rakuten", "yahoo shopping", "cart", "購入", "注文"],
    domains: [
      "amazon.co.jp", "amazon.com", "rakuten.co.jp",
      "shopping.yahoo.co.jp", "mercari.com",
    ],
  },
  {
    name: "ニュース・情報",
    keywords: ["news", "nhk", "asahi", "nikkei", "bloomberg", "朝日", "日経"],
    domains: [
      "nhk.or.jp", "asahi.com", "nikkei.com", "bloomberg.co.jp",
      "yomiuri.co.jp", "mainichi.jp",
    ],
  },
];

/**
 * タブリストを自動分類提案する
 *
 * アルゴリズム:
 * 1. 各タブのURLドメインとタイトルを CATEGORY_RULES と照合
 * 2. マッチしたルールのカテゴリに割り当て
 * 3. マッチしないタブはドメイン単位でグルーピング（フォールバック）
 * 4. 提案グループに1タブしかない場合は "その他" にまとめる
 *
 * @param {Array<chrome.tabs.Tab>} tabs - 分類対象タブの配列
 * @returns {Array<{suggestedName: string, tabs: Array<chrome.tabs.Tab>}>}
 */
function suggestClassification(tabs) {
  // カテゴリ名 => タブ配列 のマップ
  const categoryMap = new Map();

  for (const tab of tabs) {
    const domain = extractDomain(tab.url || "");
    const titleLower = (tab.title || "").toLowerCase();
    const domainLower = domain.toLowerCase();

    let matched = false;

    for (const rule of CATEGORY_RULES) {
      const domainMatch = rule.domains.some((d) => domainLower.includes(d));
      const keywordMatch = rule.keywords.some(
        (kw) => titleLower.includes(kw) || domainLower.includes(kw)
      );

      if (domainMatch || keywordMatch) {
        if (!categoryMap.has(rule.name)) {
          categoryMap.set(rule.name, []);
        }
        categoryMap.get(rule.name).push(tab);
        matched = true;
        break; // 最初にマッチしたルールを採用
      }
    }

    // フォールバック: ルール未マッチの場合はドメイン名をグループ名に
    if (!matched && domain) {
      if (!categoryMap.has(domain)) {
        categoryMap.set(domain, []);
      }
      categoryMap.get(domain).push(tab);
    }
  }

  // 結果を配列化。1タブのみのドメイングループは "その他" に統合
  const suggestions = [];
  const others = [];

  for (const [name, groupTabs] of categoryMap.entries()) {
    // ルール定義されたカテゴリは1タブでも独立グループとして表示
    const isRuleCategory = CATEGORY_RULES.some((r) => r.name === name);

    if (!isRuleCategory && groupTabs.length === 1) {
      others.push(...groupTabs);
    } else {
      suggestions.push({ suggestedName: name, tabs: groupTabs });
    }
  }

  if (others.length > 0) {
    suggestions.push({ suggestedName: "その他", tabs: others });
  }

  // タブ数の多い順にソート
  suggestions.sort((a, b) => b.tabs.length - a.tabs.length);

  return suggestions;
}

window.ClassifierModule = {
  extractDomain,
  suggestClassification,
};
```

---

## ⑤ ポップアップUI（HTML）

```html
<!-- popup/popup.html -->
<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Tab Group Manager</title>
  <link rel="stylesheet" href="popup.css" />
</head>
<body>

  <!-- ヘッダー -->
  <header class="app-header">
    <h1 class="app-title">Tab Group Manager</h1>
  </header>

  <!-- メインコンテンツ -->
  <main class="app-main">

    <!-- グループ作成フォーム -->
    <section class="create-group-section">
      <div class="input-row">
        <input
          type="text"
          id="groupNameInput"
          class="text-input"
          placeholder="グループ名を入力..."
          maxlength="50"
        />
        <button id="createGroupBtn" class="btn btn-primary">作成</button>
      </div>
    </section>

    <!-- アクションボタン群 -->
    <section class="action-section">
      <button id="suggestBtn" class="btn btn-secondary btn-full">
        🤖 自動分類提案
      </button>
    </section>

    <!-- エラー・通知メッセージ表示エリア -->
    <div id="messageArea" class="message-area" role="alert" aria-live="polite"></div>

    <!-- 自動分類提案結果エリア（初期非表示） -->
    <section id="suggestionSection" class="suggestion-section hidden">
      <h2 class="section-title">📋 分類提案</h2>
      <p class="section-desc">以下のグループ案を一括作成できます</p>
      <div id="suggestionList" class="suggestion-list"></div>
      <div class="suggestion-actions">
        <button id="applySuggestionsBtn" class="btn btn-primary">
          ✅ 選択した提案を適用
        </button>
        <button id="cancelSuggestionsBtn" class="btn btn-ghost">
          キャンセル
        </button>
      </div>
    </section>

    <!-- グループ一覧 -->
    <section class="groups-section">
      <h2 class="section-title">
        グループ一覧
        <span id="groupCount" class="badge">0</span>
      </h2>
      <div id="groupList" class="group-list">
        <!-- グループカードが動的に生成される -->
        <p id="emptyState" class="empty-state">
          グループがありません。<br />上のフォームから作成してください。
        </p>
      </div>
    </section>

  </main>

  <!-- スクリプト読み込み（依存順） -->
  <script src="../js/storage.js"></script>
  <script src="../js/tabManager.js"></script>
  <script src="../js/classifier.js"></script>
  <script src="popup.js"></script>

</body>
</html>
```

---

## ⑥ ポップアップCSS

```css
/* popup/popup.css */

/* ===== リセット・基本設定 ===== */
*, *::before, *::after {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

body {
  width: 420px;
  min-height: 300px;
  max-height: 600px;
  overflow-y: auto;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  font-size: 13px;
  color: #333;
  background: #f5f7fa;
}

/* ===== ヘッダー ===== */
.app-header {
  background: #2c3e50;
  color: #fff;
  padding: 10px 14px;
  position: sticky;
  top: 0;
  z-index: 10;
}

.app-title {
  font-size: 14px;
  font-weight: 600;
  letter-spacing: 0.3px;
}

/* ===== メインコンテンツ ===== */
.app-main {
  padding: 10px 12px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

/* ===== 入力フォーム ===== */
.input-row {
  display: flex;
  gap: 6px;
}

.text-input {
  flex: 1;
  padding: 6px 10px;
  border: 1px solid #ccc;
  border-radius: 6px;
  font-size: 13px;
  outline: none;
  transition: border-color 0.15s;
}

.text-input:focus {
  border-color: #4A90D9;
}

/* ===== ボタン共通 ===== */
.btn {
  padding: 6px 12px;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 12px;
  font-weight: 500;
  transition: background 0.15s, opacity 0.15s;
  white-space: nowrap;
}

.btn:hover { opacity: 0.85; }
.btn:active { opacity: 0.7; }

.btn-primary   { background: #4A90D9; color: #fff; }
.btn-secondary { background: #6c757d; color: #fff; }
.btn-danger    { background: #e74c3c; color: #fff; }
.btn-ghost     { background: transparent; color: #555; border: 1px solid #ccc; }
.btn-sm        { padding: 3px 8px; font-size: 11px; }
.btn-full      { width: 100%; }

/* ===== メッセージエリア ===== */
.message-area {
  min-height: 0;
  font-size: 12px;
  padding: 0;
  border-radius: 4px;
  transition: all 0.2s;
}

.message-area.info  { padding: 6px 10px; background: #d4edda; color: #155724; }
.message-area.error { padding: 6px 10px; background: #f8d7da; color: #721c24; }
.message-area.warn  { padding: 6px 10px; background: #fff3cd; color: #856404; }

/* ===== セクション共通 ===== */
.section-title {
  font-size: 12px;
  font-weight: 600;
  color: #555;
  margin-bottom: 6px;
  display: flex;
  align-items: center;
  gap: 6px;
}

.badge {
  background: #4A90D9;
  color: #fff;
  border-radius: 10px;
  padding: 1px 7px;
  font-size: 10px;
}

.section-desc {
  font-size: 11px;
  color: #777;
  margin-bottom: 8px;
}

/* ===== 自動分類提案セクション ===== */
.suggestion-section {
  background: #fff;
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  padding: 10px;
}

.suggestion-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-bottom: 8px;
  max-height: 160px;
  overflow-y: auto;
}

.suggestion-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 8px;
  background: #f0f4ff;
  border-radius: 6px;
  font-size: 12px;
}

.suggestion-item input[type="checkbox"] {
  cursor: pointer;
}

.suggestion-item label {
  flex: 1;
  cursor: pointer;
}

.suggestion-tab-count {
  color: #888;
  font-size: 11px;
}

.suggestion-actions {
  display: flex;
  gap: 6px;
  justify-content: flex-end;
}

/* ===== グループ一覧 ===== */
.group-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.empty-state {
  text-align: center;
  color: #aaa;
  font-size: 12px;
  padding: 20px 0;
  line-height: 1.6;
}

/* ===== グループカード ===== */
.group-card {
  background: #fff;
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  overflow: hidden;
  /* アクセントカラーを左ボーダーで表示 */
  border-left: 4px solid var(--group-color, #4A90D9);
}

.group-card-header {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 10px;
  cursor: pointer;
  user-select: none;
  background: #fafafa;
}

.group-card-header:hover {
  background: #f0f4ff;
}

.group-toggle-icon {
  font-size: 10px;
  color: #999;
  transition: transform 0.2s;
  flex-shrink: 0;
}

.group-toggle-icon.expanded {
  transform: rotate(90deg);
}

.group-name {
  flex: 1;
  font-weight: 600;
  font-size: 13px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.group-name-input {
  flex: 1;
  font-weight: 600;
  font-size: 13px;
  border: 1px solid #4A90D9;
  border-radius: 4px;
  padding: 1px 6px;
  outline: none;
}

.group-tab-count {
  font-size: 10px;
  color: #888;
  flex-shrink: 0;
}

.group-card-actions {
  display: flex;
  gap: 4px;
  flex-shrink: 0;
}

/* グループカード ボディ（タブリスト） */
.group-card-body {
  padding: 6px 10px;
  border-top: 1px solid #f0f0f0;
  display: none; /* デフォルトは折りたたみ */
}

.group-card-body.expanded {
  display: block;
}

/* グループ操作ボタン行 */
.group-card-ops {
  display: flex;
  gap: 6px;
  margin-bottom: 8px;
  flex-wrap: wrap;
}

/* タブリスト */
.tab-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
  max-height: 180px;
  overflow-y: auto;
}

.tab-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 6px;
  border-radius: 4px;
  font-size: 11px;
  background: #f5f7fa;
}

.tab-item:hover {
  background: #e8f0fe;
}

.tab-favicon {
  width: 14px;
  height: 14px;
  flex-shrink: 0;
  border-radius: 2px;
  /* favicon読み込み失敗時のフォールバック */
  object-fit: contain;
}

.tab-title {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: #333;
  cursor: pointer;
  text-decoration: none;
}

.tab-title:hover {
  text-decoration: underline;
  color: #4A90D9;
}

.tab-remove-btn {
  flex-shrink: 0;
  background: none;
  border: none;
  cursor: pointer;
  color: #ccc;
  font-size: 13px;
  line-height: 1;
  padding: 0 2px;
}

.tab-remove-btn:hover {
  color: #e74c3c;
}

/* 復元トグル */
.restore-toggle-row {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 8px;
  padding-top: 6px;
  border-top: 1px solid #f0f0f0;
  font-size: 11px;
  color: #666;
}

/* ===== ユーティリティ ===== */
.hidden { display: none !important; }
```

---

## ⑦ ポップアップロジック（メイン）

```js
// ======================================================
// popup/popup.js
// ポップアップUIのすべてのロジックを担う中心モジュール
// ======================================================

// ===== DOM要素の取得 =====
const $ = (id) => document.getElementById(id);

const groupNameInput    = $("groupNameInput");
const createGroupBtn    = $("createGroupBtn");
const groupList         = $("groupList");
const groupCount        = $("groupCount");
const emptyState        = $("emptyState");
const messageArea       = $("messageArea");
const suggestBtn        = $("suggestBtn");
const suggestionSection = $("suggestionSection");
const suggestionList    = $("suggestionList");
const applySuggestionsBtn  = $("applySuggestionsBtn");
const cancelSuggestionsBtn = $("cancelSuggestionsBtn");

// ===== モジュール参照（グローバル名前空間から取得）=====
const Storage    = window.StorageModule;
const TabManager = window.TabManagerModule;
const Classifier = window.ClassifierModule;

// ===== 内部状態 =====
// 提案結果を一時保持（適用ボタン押下まで保持）
let pendingSuggestions = [];

// ===== ユーティリティ =====

/**
 * メッセージエリアにメッセージを表示する
 * @param {string} text
 * @param {"info"|"error"|"warn"} type
 * @param {number} [duration=3000] 自動消去時間(ms) / 0なら消去しない
 */
function showMessage(text, type = "info", duration = 3000) {
  messageArea.textContent = text;
  messageArea.className = `message-area ${type}`;

  if (duration > 0) {
    setTimeout(() => {
      messageArea.textContent = "";
      messageArea.className = "message-area";
    }, duration);
  }
}

/**
 * faviconのロード失敗時にデフォルト画像を設定する
 * @param {HTMLImageElement} imgEl
 */
function onFaviconError(imgEl) {
  imgEl.src =
    "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'%3E%3Ccircle cx='8' cy='8' r='7' fill='%23ccc'/%3E%3C/svg%3E";
}

// ===== メイン描画ロジック =====

/**
 * グループ一覧を全再描画する
 * パフォーマンス: 100タブ以下の想定のため仮想スクロール等は不使用
 */
async function renderGroups() {
  const groups = await Storage.getAllGroups();
  const groupArray = Object.values(groups).sort(
    (a, b) => a.createdAt - b.createdAt  // 作成順に表示
  );

  // カウントバッジ更新
  groupCount.textContent = groupArray.length;

  // 既存DOMをクリア
  groupList.innerHTML = "";

  if (groupArray.length === 0) {
    groupList.appendChild(emptyState);
    emptyState.classList.remove("hidden");
    return;
  }

  emptyState.classList.add("hidden");

  for (const group of groupArray) {
    const card = createGroupCard(group);
    groupList.appendChild(card);
  }
}

/**
 * グループカードDOMを生成する
 * @param {Object} group - ストレージグループオブジェクト
 * @returns {HTMLElement}
 */
function createGroupCard(group) {
  const card = document.createElement("div");
  card.className = "group-card";
  card.style.setProperty("--group-color", group.color || "#4A90D9");
  card.dataset.groupId = group.id;

  // ----- ヘッダー部分 -----
  const header = document.createElement("div");
  header.className = "group-card-header";
  header.title = "クリックで展開/折りたたみ";

  const toggleIcon = document.createElement("span");
  toggleIcon.className = "group-toggle-icon";
  toggleIcon.textContent = "▶";

  const groupNameEl = document.createElement("span");
  groupNameEl.className = "group-name";
  groupNameEl.textContent = group.name;

  const tabCountEl = document.createElement("span");
  tabCountEl.className = "group-tab-count";
  tabCountEl.textContent = `${group.tabs.length}タブ`;

  // ヘッダーアクションボタン
  const headerActions = document.createElement("div");
  headerActions.className = "group-card-actions";

  const editBtn = document.createElement("button");
  editBtn.className = "btn btn-sm btn-ghost";
  editBtn.textContent = "✏️";
  editBtn.title = "グループ名を編集";

  const deleteBtn = document.createElement("button");
  deleteBtn.className = "btn btn-sm btn-danger";
  deleteBtn.textContent = "🗑";
  deleteBtn.title = "グループを削除";

  headerActions.appendChild(editBtn);
  headerActions.appendChild(deleteBtn);

  header.appendChild(toggleIcon);
  header.appendChild(groupNameEl);
  header.appendChild(tabCountEl);
  header.appendChild(headerActions);

  // ----- ボディ部分 -----
  const body = document.createElement("div");
  body.className = "group-card-body";

  // 操作ボタン行
  const opsRow = document.createElement("div");
  opsRow.className = "group-card-ops";

  const addCurrentTabBtn = document.createElement("button");
  addCurrentTabBtn.className = "btn btn-sm btn-primary";
  addCurrentTabBtn.textContent = "現在のタブを追加";

  const openAllBtn = document.createElement("button");
  openAllBtn.className = "btn btn-sm btn-secondary";
  openAllBtn.textContent = "全タブを開く";

  opsRow.appendChild(addCurrentTabBtn);
  opsRow.appendChild(openAllBtn);

  // タブリスト
  const tabListEl = document.createElement("div");
  tabListEl.className = "tab-list";
  renderTabList(group, tabListEl);

  // 復元トグル
  const restoreRow = document.createElement("div");
  restoreRow.className = "restore-toggle-row";

  const restoreCheckbox = document.createElement("input");
  restoreCheckbox.type = "checkbox";
  restoreCheckbox.id = `restore-${group.id}`;
  restoreCheckbox.checked = group.restoreEnabled;

  const restoreLabel = document.createElement("label");
  restoreLabel.htmlFor = `restore-${group.id}`;
  restoreLabel.textContent = "再起動時に自動復元する";

  restoreRow.appendChild(restoreCheckbox);
  restoreRow.appendChild(restoreLabel);

  body.appendChild(opsRow);
  body.appendChild(tabListEl);
  body.appendChild(restoreRow);

  // ----- 組み立て -----
  card.appendChild(header);
  card.appendChild(body);

  // ===== イベントリスナー登録 =====

  // 展開/折りたたみ（ボタン以外の領域をクリック時）
  header.addEventListener("click", (e) => {
    if (e.target === editBtn || e.target === deleteBtn) return;
    const isExpanded = body.classList.toggle("expanded");
    toggleIcon.classList.toggle("expanded", isExpanded);
  });

  // グループ名編集
  editBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    startEditGroupName(group.id, groupNameEl, editBtn);
  });

  // グループ削除
  deleteBtn.addEventListener("click", async (e) => {
    e.stopPropagation();
    await handleDeleteGroup(group.id, group.name);
  });

  // 現在のタブを追加
  addCurrentTabBtn.addEventListener("click", async () => {
    await handleAddCurrentTab(group.id, tabListEl, tabCountEl);
  });

  // 全タブを開く
  openAllBtn.addEventListener("click", async () => {
    await handleOpenAllTabs(group);
  });

  // 復元フラグ更新
  restoreCheckbox.addEventListener("change", async () => {
    await Storage.updateRestoreEnabled(group.id, restoreCheckbox.checked);
    showMessage(
      `"${group.name}" の自動復元を${restoreCheckbox.checked ? "有効" : "無効"}にしました`,
      "info"
    );
  });

  return card;
}

/**
 * タブリスト部分を描画する（カード内の再描画にも使用）
 * @param {Object} group
 * @param {HTMLElement} containerEl
 */
function renderTabList(group, containerEl) {
  containerEl.innerHTML = "";

  if (group.tabs.length === 0) {
    const emptyMsg = document.createElement("p");
    emptyMsg.style.cssText = "text-align:center;color:#bbb;font-size:11px;padding:8px 0";
    emptyMsg.textContent = "タブがありません";
    containerEl.appendChild(emptyMsg);
    return;
  }

  for (const tab of group.tabs) {
    const item = createTabItem(group.id, tab, containerEl, group);
    containerEl.appendChild(item);
  }
}

/**
 * タブアイテムDOMを生成する
 * @param {string} groupId
 * @param {Object} tab - ストレージタブオブジェクト
 * @param {HTMLElement} containerEl - 再描画用の親コンテナ
 * @param {Object} group - 親グループ（再描画用）
 * @returns {HTMLElement}
 */
function createTabItem(groupId, tab, containerEl, group) {
  const item = document.createElement("div");
  item.className = "tab-item";
  item.dataset.tabId = tab.id;

  // Favicon
  const favicon = document.createElement("img");
  favicon.className = "tab-favicon";
  favicon.src = tab.favicon || "";
  favicon.alt = "";
  favicon.onerror = () => onFaviconError(favicon);

  // タイトルリンク（クリックでChromeタブを開く）
  const titleEl = document.createElement("a");
  titleEl.className = "tab-title";
  titleEl.textContent = tab.title || tab.url;
  titleEl.title = tab.url;
  titleEl.href = "#";
  titleEl.addEventListener("click", (e) => {
    e.preventDefault();
    chrome.tabs.create({ url: tab.url, active: true });
  });

  // 削除ボタン
  const removeBtn = document.createElement("button");
  removeBtn.className = "tab-remove-btn";
  removeBtn.textContent = "✕";
  removeBtn.title = "グループから削除";
  removeBtn.addEventListener("click", async () => {
    await handleRemoveTab(groupId, tab.id, containerEl, group);
  });

  item.appendChild(favicon);
  item.appendChild(titleEl);
  item.appendChild(removeBtn);

  return item;
}

// ===== イベントハンドラ =====

/**
 * グループ作成ハンドラ
 */
async function handleCreateGroup() {
  const name = groupNameInput.value.trim();

  if (!name) {
    showMessage("グループ名を入力してください", "warn");
    groupNameInput.focus();
    return;
  }

  if (name.length > 50) {
    showMessage("グループ名は50文字以内にしてください", "warn");
    return;
  }

  try {
    createGroupBtn.disabled = true;
    await Storage.createGroup(name);
    groupNameInput.value = "";
    showMessage(`グループ "${name}" を作成しました`, "info");
    await renderGroups();
  } catch (err) {
    showMessage(`エラー: ${err.message}`, "error", 0);
    console.error("[createGroup]", err);
  } finally {
    createGroupBtn.disabled = false;
  }
}

/**
 * グループ名インライン編集開始
 * @param {string} groupId
 * @param {HTMLElement} nameEl - 名前表示要素
 * @param {HTMLElement} editBtn
 */
function startEditGroupName(groupId, nameEl, editBtn) {
  const input = document.createElement("input");
  input.className = "group-name-input";
  input.type = "text";
  input.value = nameEl.textContent;
  input.maxLength = 50;

  nameEl.replaceWith(input);
  input.focus();
  input.select();
  editBtn.textContent = "💾";
  editBtn.title = "保存";

  // 保存処理
  const save = async () => {
    const newName = input.value.trim();
    if (!newName) {
      showMessage("グループ名を入力してください", "warn");
      input.focus();
      return;
    }
    try {
      await Storage.updateGroupName(groupId, newName);
      showMessage(`グループ名を "${newName}" に変更しました`, "info");
      await renderGroups();
    } catch (err) {
      showMessage(`エラー: ${err.message}`, "error", 0);
      console.error("[updateGroupName]", err);
    }
  };

  // Enterキーで保存
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter") save();
    if (e.key === "Escape") renderGroups(); // キャンセル
  });

  // 保存ボタンの動作を上書き
  editBtn.onclick = (e) => {
    e.stopPropagation();
    save();
  };
}

/**
 * グループ削除ハンドラ
 * @param {string} groupId
 * @param {string} groupName
 */
async function handleDeleteGroup(groupId, groupName) {
  if (!confirm(`グループ "${groupName}" を削除しますか？\nタブURLの記録も全て削除されます。`)) {
    return;
  }

  try {
    await Storage.deleteGroup(groupId);
    showMessage(`グループ "${groupName}" を削除しました`, "info");
    await renderGroups();
  } catch (err) {
    showMessage(`エラー: ${err.message}`, "error", 0);
    console.error("[deleteGroup]", err);
  }
}

/**
 * 現在アクティブなタブをグループに追加するハンドラ
 * @param {string} groupId
 * @param {HTMLElement} tabListEl
 * @param {HTMLElement} tabCountEl
 */
async function handleAddCurrentTab(groupId, tabListEl, tabCountEl) {
  try {
    const activeTab = await TabManager.getActiveTab();
    const tabInfo = TabManager.chromeTabToTabInfo(activeTab);

    if (!tabInfo.url) {
      showMessage("このタブのURLを取得できません（chrome://ページは追加不可）", "warn");
      return;
    }

    const savedTab = await Storage.addTabToGroup(groupId, tabInfo);

    // 全再描画ではなく、タブリスト部分のみ更新（UX改善）
    const groups = await Storage.getAllGroups();
    const group = groups[groupId];
    renderTabList(group, tabListEl);
    tabCountEl.textContent = `${group.tabs.length}タブ`;

    showMessage(`"${tabInfo.title || tabInfo.url}" を追加しました`, "info");
  } catch (err) {
    if (err.message.includes("already exists")) {
      showMessage("このタブはすでにグループに登録されています", "warn");
    } else {
      showMessage(`エラー: ${err.message}`, "error", 0);
      console.error("[addCurrentTab]", err);
    }
  }
}

/**
 * タブをグループから削除するハンドラ
 * @param {string} groupId
 * @param {string} tabId
 * @param {HTMLElement} containerEl
 * @param {Object} group
 */
async function handleRemoveTab(groupId, tabId, containerEl, group) {
  try {
    await Storage.removeTabFromGroup(groupId, tabId);
    // タブリスト部分のみ再描画
    const groups = await Storage.getAllGroups();
    const updatedGroup = groups[groupId];
    renderTabList(updatedGroup, containerEl);

    // タブカウント更新
    const card = containerEl.closest(".group-card");
    if (card) {
      const countEl = card.querySelector(".group-tab-count");
      if (countEl) countEl.textContent = `${updatedGroup.tabs.length}タブ`;
    }

    showMessage("タブをグループから削除しました", "info");
  } catch (err) {
    showMessage(`エラー: ${err.message}`, "error", 0);
    console.error("[removeTab]", err);
  }
}

/**
 * グループ内の全タブを開くハンドラ
 * @param {Object} group
 */
async function handleOpenAllTabs(group) {
  if (group.tabs.length === 0) {
    showMessage("このグループにはタブがありません", "warn");
    return;
  }

  try {
    await TabManager.openGroupTabs(group.tabs);
    showMessage(`${group.tabs.length}タブを開きました`, "info");
  } catch (err) {
    showMessage(`エラー: ${err.message}`, "error", 0);
    console.error("[openAllTabs]", err);
  }
}

// ===== 自動分類提案 =====

/**
 * 自動分類提案ボタン押下ハンドラ
 */
async function handleSuggest() {
  try {
    suggestBtn.disabled = true;
    suggestBtn.textContent = "🔍 分析中...";

    const currentTabs = await TabManager.getCurrentWindowTabs();

    // chrome://ページなど分類不可のタブを除外
    const classifiableTabs = currentTabs.filter(
      (t) => t.url && !t.url.startsWith("chrome://") && !t.url.startsWith("chrome-extension://")
    );

    if (classifiableTabs.length === 0) {
      showMessage("分類可能なタブがありません", "warn");
      return;
    }

    pendingSuggestions = Classifier.suggestClassification(classifiableTabs);
    renderSuggestions(pendingSuggestions);
    suggestionSection.classList.remove("hidden");

  } catch (err) {
    showMessage(`提案エラー: ${err.message}`, "error", 0);
    console.error("[suggest]", err);
  } finally {
    suggestBtn.disabled = false;
    suggestBtn.textContent = "🤖 自動分類提案";
  }
}

/**
 * 提案リストをレンダリングする
 * @param {Array<{suggestedName: string, tabs: Array}>} suggestions
 */
function renderSuggestions(suggestions) {
  suggestionList.innerHTML = "";

  for (let i = 0; i < suggestions.length; i++) {
    const suggestion = suggestions[i];

    const item = document.createElement("div");
    item.className = "suggestion-item";

    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.id = `suggest-${i}`;
    checkbox.dataset.suggestionIndex = i;
    checkbox.checked = true; // デフォルトは全選択

    const label = document.createElement("label");
    label.htmlFor = `suggest-${i}`;
    label.textContent = suggestion.suggestedName;

    const countEl = document.createElement("span");
    countEl.className = "suggestion-tab-count";
    countEl.textContent = `${suggestion.tabs.length}タブ`;

    // タブタイトル一覧をtitleで確認できるようにする
    item.title = suggestion.tabs.map((t) => t.title || t.url).join("\n");

    item.appendChild(checkbox);
    item.appendChild(label);
    item.appendChild(countEl);
    suggestionList.appendChild(item);
  }
}

/**
 * 提案を適用してグループを一括作成するハンドラ
 */
async function handleApplySuggestions() {
  const checkboxes = suggestionList.querySelectorAll('input[type="checkbox"]:checked');
  const selectedIndices = Array.from(checkboxes).map(
    (cb) => parseInt(cb.dataset.suggestionIndex, 10)
  );

  if (selectedIndices.length === 0) {
    showMessage("少なくとも1つの提案を選択してください", "warn");
    return;
  }

  let createdCount = 0;
  let skippedCount = 0;

  try {
    applySuggestionsBtn.disabled = true;
    applySuggestionsBtn.textContent = "作成中...";

    for (const idx of selectedIndices) {
      const suggestion = pendingSuggestions[idx];
      const newGroup = await Storage.createGroup(suggestion.suggestedName);

      for (const chromeTab of suggestion.tabs) {
        const tabInfo = TabManager.chromeTabToTabInfo(chromeTab);
        if (!tabInfo.url) continue;

        try {
          await Storage.addTabToGroup(newGroup.id, tabInfo);
          createdCount++;
        } catch {
          // 重複エラーは無視してスキップ
          skippedCount++;
        }
      }
    }

    showMessage(
      `${selectedIndices.length}グループを作成（タブ${createdCount}件追加${skippedCount > 0 ? ` / ${skippedCount}件スキップ` : ""}）`,
      "info",
      5000
    );

    suggestionSection.classList.add("hidden");
    pendingSuggestions = [];
    await renderGroups();

  } catch (err) {
    showMessage(`グループ作成エラー: ${err.message}`, "error", 0);
    console.error("[applySuggestions]", err);
  } finally {
    applySuggestionsBtn.disabled = false;
    applySuggestionsBtn.textContent = "✅ 選択した提案を適用";
  }
}

// ===== グローバルイベント登録 =====

// グループ作成ボタン
createGroupBtn.addEventListener("click", handleCreateGroup);

// Enterキーでグループ作成
groupNameInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter") handleCreateGroup();
});

// 自動分類提案ボタン
suggestBtn.addEventListener("click", handleSuggest);

// 提案適用ボタン
applySuggestionsBtn.addEventListener("click", handleApplySuggestions);

// 提案キャンセルボタン
cancelSuggestionsBtn.addEventListener("click", () => {
  suggestionSection.classList.add("hidden");
  pendingSuggestions = [];
});

// ===== 初期化 =====
(async () => {
  try {
    await renderGroups();
  } catch (err) {
    showMessage(`初期化エラー: ${err.message}`, "error", 0);
    console.error("[init]", err);
  }
})();
```

---

## ⑧ バックグラウンドService Worker（自動復元）

```js
// ======================================================
// background.js
// Manifest V3 Service Worker
// Chrome起動時のタブ自動復元を担当する
//
// 設計原則:
//   - 常駐処理は行わない（SW制限への対応）
//   - onStartup / onInstalled イベントのみで動作する
//   - ストレージ操作はchrome.storage APIを直接使用
//     （storage.jsのwindow依存コードはSWでは動作しないため）
// ======================================================

const STORAGE_KEY = "groups";
// 復元タブの上限数（リスク対策: 大量タブによるブラウザ重停止を防止）
const MAX_RESTORE_TABS_PER_GROUP = 20;
// 全グループ合計の復元タブ上限
const MAX_RESTORE_TABS_TOTAL = 50;

/**
 * ストレージから全グループを取得する（SW専用実装）
 * @returns {Promise<Object>}
 */
function getGroupsFromStorage() {
  return new Promise((resolve, reject) => {
    chrome.storage.local.get(STORAGE_KEY, (result) => {
      if (chrome.runtime.lastError) {
        reject(new Error(chrome.runtime.lastError.message));
        return;
      }
      resolve(result[STORAGE_KEY] ?? {});
    });
  });
}

/**
 * restoreEnabled=true のグループのタブを自動復元する
 *
 * 復元フロー:
 * 1. ストレージからグループを全取得
 * 2. restoreEnabled=true のグループを抽出
 * 3. 各グループのタブURLを上限以内で新規タブとして開く
 * 4. 復元完了ログを記録（デバッグ用）
 *
 * @returns {Promise<void>}
 */
async function restoreAllGroups() {
  console.log("[TabGroupManager] Starting auto-restore...");

  let groups;
  try {
    groups = await getGroupsFromStorage();
  } catch (err) {
    console.error("[TabGroupManager] Failed to load groups:", err);
    return;
  }

  const restoreTargetGroups = Object.values(groups).filter(
    (g) => g.restoreEnabled && g.tabs && g.tabs.length > 0
  );

  if (restoreTargetGroups.length === 0) {
    console.log("[TabGroupManager] No groups to restore.");
    return;
  }

  console.log(
    `[TabGroupManager] Restoring ${restoreTargetGroups.length} group(s)...`
  );

  let totalRestoredCount = 0;

  for (const group of restoreTargetGroups) {
    if (totalRestoredCount >= MAX_RESTORE_TABS_TOTAL) {
      console.warn(
        `[TabGroupManager] Total restore limit (${MAX_RESTORE_TABS_TOTAL}) reached. Skipping remaining groups.`
      );
      break;
    }

    // 復元可能なURLのみ抽出
    const restorableUrls = group.tabs
      .slice(0, MAX_RESTORE_TABS_PER_GROUP)
      .map((t) => t.url)
      .filter(
        (url) =>
          url &&
          !url.startsWith("chrome://") &&
          !url.startsWith("chrome-extension://") &&
          !url.startsWith("about:")
      )
      .slice(0, MAX_RESTORE_TABS_TOTAL - totalRestoredCount); // 合計上限を超えないようにクリップ

    if (restorableUrls.length === 0) {
      console.log(
        `[TabGroupManager] Group "${group.name}": No restorable URLs.`
      );
      continue;
    }

    console.log(
      `[TabGroupManager] Restoring group "${group.name}": ${restorableUrls.length} tab(s)`
    );

    // タブを順次開く（並列だとChromeに負荷がかかるため逐次処理）
    for (const url of restorableUrls) {
      try {
        await new Promise((resolve, reject) => {
          chrome.tabs.create({ url, active: false }, (tab) => {
            if (chrome.runtime.lastError) {
              reject(new Error(chrome.runtime.lastError.message));
            } else {
              resolve(tab);
            }
          });
        });
        totalRestoredCount++;
      } catch (err) {
        console.warn(
          `[TabGroupManager] Failed to restore tab "${url}":`,
          err.message
        );
        // 1タブの失敗で全体を中断しない
      }
    }
  }

  console.log(
    `[TabGroupManager] Auto-restore complete. Total: ${totalRestoredCount} tab(s) restored.`
  );
}

// ===== イベントリスナー =====

/**
 * Chrome起動時（デスクトップのChromeアイコンから起動）に発火
 * クラッシュ終了・タスクキルからの再起動では発火しない点に注意
 */
chrome.runtime.onStartup.addListener(() => {
  console.log("[TabGroupManager] onStartup fired.");
  restoreAllGroups().catch((err) => {
    console.error("[TabGroupManager] restoreAllGroups error:", err);
  });
});

/**
 * 拡張機能インストール・更新時に発火
 * 初回インストール時は復元対象がないためスキップされる
 * 開発中のreload時にも発火するため開発時の動作確認に活用
 */
chrome.runtime.onInstalled.addListener((details) => {
  console.log(`[TabGroupManager] onInstalled fired. reason: ${details.reason}`);
  // インストール時はデータがないため何もしない
  // "update"時もユーザーの意図しない復元になるため動作させない
});

/**
 * ポップアップからの手動復元メッセージを受信するハンドラ
 * リスク対策: onStartupが発火しないケース（クラッシュ終了等）への対応
 */
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === "MANUAL_RESTORE") {
    console.log("[TabGroupManager] Manual restore requested.");
    restoreAllGroups()
      .then(() => sendResponse({ success: true }))
      .catch((err) => {
        console.error("[TabGroupManager] Manual restore error:", err);
        sendResponse({ success: false, error: err.message });
      });
    // 非同期レスポンスのためtrueを返す
    return true;
  }
});
```

---

## ⑨ ポップアップに手動復元ボタンを追加（popup.html 追記分）

```html
<!-- popup.html の <section class="action-section"> 内に追記 -->
<section class="action-section">
  <button id="suggestBtn" class="btn btn-secondary btn-full">
    🤖 自動分類提案
  </button>
  <!-- リスク対策: onStartup非発火時の手動復元 -->
  <button id="manualRestoreBtn" class="btn btn-ghost btn-full" style="margin-top:6px">
    🔄 グループを手動復元（クラッシュ後など）
  </button>
</section>
```

```js
// popup.js に追記する手動復元ハンドラ

const manualRestoreBtn = $("manualRestoreBtn");

manualRestoreBtn.addEventListener("click", async () => {
  try {
    manualRestoreBtn.disabled = true;
    manualRestoreBtn.textContent = "復元中...";

    // background.js の MANUAL_RESTORE メッセージハンドラを呼び出す
    const response = await new Promise((resolve, reject) => {
      chrome.runtime.sendMessage({ type: "MANUAL_RESTORE" }, (res) => {
        if (chrome.runtime.lastError) {
          reject(new Error(chrome.runtime.lastError.message));
        } else {
          resolve(res);
        }
      });
    });

    if (response?.success) {
      showMessage("手動復元を実行しました", "info");
    } else {
      showMessage(`復元エラー: ${response?.error ?? "不明なエラー"}`, "error", 0);
    }
  } catch (err) {
    showMessage(`復元エラー: ${err.message}`, "error", 0);
    console.error("[manualRestore]", err);
  } finally {
    manualRestoreBtn.disabled = false;
    manualRestoreBtn.textContent = "🔄 グループを手動復元（クラッシュ後など）";
  }
});
```

---

## ⑩ データフロー・シーケンス図（テキスト形式）

```
=== グループ作成フロー ===

[User]          [popup.js]          [storage.js]       [chrome.storage.local]
  |                |                    |                        |
  |--入力+ボタン-->|                    |                        |
  |                |--createGroup()---->|                        |
  |                |                   |--getAllGroups()-------->|
  |                |                   |<--{groups:{}}---------  |
  |                |                   |--新グループ追加          |
  |                |                   |--saveAllGroups()------->|
  |                |                   |<--success-----------   |
  |                |<--newGroup obj----|                        |
  |                |--renderGroups()   |                        |
  |<--UI更新-------|                   |                        |

=== Chrome起動時自動復元フロー ===

[Chrome起動]   [background.js SW]    [chrome.storage.local]   [chrome.tabs]
  |                |                        |                       |
  |--onStartup---->|                        |                       |
  |                |--getGroupsFromStorage->|                       |
  |                |<--groups data------    |                       |
  |                |--filter restoreEnabled=true                    |
  |                |--for each restorable URL                       |
  |                |--chrome.tabs.create()------------------------->|
  |                |                        |              新タブ表示|
  |                |<--tab object----------                        |

=== 自動分類提案フロー ===

[User]       [popup.js]        [tabManager.js]   [classifier.js]   [storage.js]
  |              |                   |                  |                |
  |--提案btn---->|                   |                  |                |
  |              |--getCurrentTabs-->|                  |                |
  |              |<--tabs[]----------                   |                |
  |              |--suggestClassification(tabs)-------->|                |
  |              |<--suggestions[]---                   |                |
  |              |--renderSuggestions()                 |                |
  |<--提案UI表示-|                   |                  |                |
  |--適用btn---->|                   |                  |                |
  |              |--createGroup()×N---------------------------------->|
  |              |--addTabToGroup()×N---------------------------------|
  |              |--renderGroups()   |                  |                |
  |<--UI更新-----|                   |                  |                |
```

---

## ⑪ 受け入れ条件チェックリスト

| # | 受け入れ条件 | 実装箇所 | 確認方法 |
|---|---|---|---|
| 1 | グループを新規作成し、任意の名前をつけられる | `storage.js:createGroup()` + `popup.js:handleCreateGroup()` | フォームに名前入力→作成ボタン |
| 2 | 現在開いているタブをグループに追加できる | `tabManager.js:getActiveTab()` + `storage.js:addTabToGroup()` | グループ展開→「現在のタブを追加」 |
| 3 | グループからタブを削除できる | `storage.js:removeTabFromGroup()` + `popup.js:handleRemoveTab()` | タブ項目の✕ボタン |
| 4 | グループ名を編集できる | `storage.js:updateGroupName()` + `popup.js:startEditGroupName()` | ✏️ボタンで編集→Enter/💾 |
| 5 | グループを削除できる | `storage.js:deleteGroup()` + `popup.js:handleDeleteGroup()` | 🗑ボタン→確認ダイアログ→削除 |
| 6 | 自動分類提案でドメイン単位のグループ案が表示される | `classifier.js:suggestClassification()` | 「自動分類提案」ボタン |
| 7 | Chrome再起動後に保存グループのタブが自動復元される | `background.js:restoreAllGroups()` + `onStartup` | 拡張機能インストール後Chrome再起動 |

---

## ⑫ インストール手順

```bash
# 1. ディレクトリ作成
mkdir tab-group-manager
cd tab-group-manager

# 2. 上記コードを対応ファイルパスに保存する

# 3. アイコン作成（任意 - なければmanifest.jsonのiconsフィールドを削除）
# icons/icon48.png に 48x48 の PNG を配置

# 4. Chrome拡張機能としてロード
# Chrome → chrome://extensions/ を開く
# 「デベロッパーモード」をONにする
# 「パッケージ化されていない拡張機能を読み込む」→ tab-group-manager フォルダを選択
# 拡張機能バーのアイコンをクリックしてポップアップを確認
```

---

## ⑬ 既知の制約と今後の改善ポイント

| 項目 | 現状 | 改善案 |
|---|---|---|
| `chrome://`ページ | 追加・復元不可（セキュリティ制約） | ユーザーに明示的なメッセージ表示済み |
| SW非アクティブ終了 | `onStartup`のみ使用で回避済み | 問題が出た場合は`chrome.alarms`を検討 |
| storage容量超過 | エラー時はcatch→showMessageで通知 | 5MB超過検知ロジックの追加を推奨 |
| タブ重複管理 | 同一URL重複追加を防止済み | 複数グループへの同一URL登録は許容 |
| 復元ウィンドウ | 現在のウィンドウに追加 | `restoreEnabled`単位で設定できるよう拡張可能 |

---

## 🔍 QA検証・デバッグレポート
# 検証報告書：Chrome拡張機能「TabGroup Manager」

---

## 総合評価

| 観点 | 重大度 | 件数 |
|---|---|---|
| **致命的不整合（動作不能レベル）** | 🔴 Critical | 5件 |
| **バグ・エッジケース不具合** | 🟠 High | 9件 |
| **セキュリティ脆弱性** | 🟡 Medium | 4件 |
| **設計上の懸念・改善推奨** | 🔵 Low | 6件 |

**結論: フロントエンド実装とバックエンド実装は「同一拡張機能の2つの独立した実装案」であり、そのまま結合すると動作しません。** 以下に全問題点と修正案を示します。

---

## セクション1: フロントエンド⇔バックエンド間の致命的不整合

### 🔴 C-01: モジュールシステムの根本的不一致

**問題:**
フロントエンド実装は ES Modules（`import/export`）を使用し、バックエンド実装は `window.StorageModule` によるグローバル名前空間パターンを使用しています。

| 項目 | フロントエンド | バックエンド |
|---|---|---|
| モジュール方式 | `export async function loadData()` | `window.StorageModule = { ... }` |
| 読み込み方法 | `import { loadData } from '../js/storage.js'` | `<script src="../js/storage.js">` |
| manifest.json | `"type": "module"` あり | `"type": "module"` なし |
| popup.html script | `<script type="module">` | `<script>`（通常スクリプト） |

**影響:** 2つの実装を混在させると、片方のモジュールが読み込めず全機能が停止します。

**修正方針:**
どちらか一方に統一する必要があります。Manifest V3のService Workerは ES Modules をサポートしているため、**フロントエンド方式（ES Modules）に統一**することを推奨します。

```javascript
// ❌ バックエンド方式（Service Workerでwindowは未定義）
window.StorageModule = { getAllGroups, createGroup, ... };

// ✅ ES Modules方式に統一
export { getAllGroups, createGroup, ... };
```

```json
// manifest.json も統一
{
  "background": {
    "service_worker": "background.js",
    "type": "module"  // ← 必須
  }
}
```

---

### 🔴 C-02: ストレージキー・スキーマの不一致

**問題:**
フロントエンドとバックエンドでストレージのルートキーとデータ構造が異なります。

```javascript
// フロントエンド（storage.js）
const STORAGE_KEY = 'tabGroupManager';
// 保存構造:
{
  "tabGroupManager": {
    "groups": { ... },
    "settings": {
      "autoRestoreOnStartup": true,
      "maxRestoreTabsPerGroup": 20
    }
  }
}

// バックエンド（storage.js + background.js）
const STORAGE_KEY = "groups";   // ← キーが違う
const StorageKeys = { GROUPS: "groups" };
// 保存構造:
{
  "groups": { ... }  // settingsオブジェクトが存在しない
}
```

| 差異 | フロントエンド | バックエンド |
|---|---|---|
| ルートキー | `tabGroupManager` | `groups` |
| settings | `settings`オブジェクトあり | なし |
| 復元フラグ | `settings.autoRestoreOnStartup`（全体） | `group.restoreEnabled`（グループ別） |
| collapsed状態 | `group.collapsed`あり | なし |
| ID生成 | `Date.now().toString(36)-random` | `g-Date.now()-random` / `t-Date.now()-random` |

**影響:** popup.jsが保存したデータをbackground.jsが読めない（キーが違うため空オブジェクトが返る）。復元が一切動作しません。

**修正コード（統一スキーマ）:**

```javascript
// 統一ストレージスキーマ
const STORAGE_KEY = 'tabGroupManager';

// 統一データ構造
{
  "tabGroupManager": {
    "groups": {
      "<groupId>": {
        "id": string,
        "name": string,
        "color": string,
        "collapsed": boolean,        // UI状態の永続化
        "restoreEnabled": boolean,   // グループ別復元フラグ（バックエンドの良い設計を採用）
        "createdAt": number,
        "tabs": [
          {
            "id": string,
            "url": string,
            "title": string,
            "favicon": string,
            "addedAt": number
          }
        ]
      }
    },
    "settings": {
      "autoRestoreOnStartup": boolean,
      "maxRestoreTabsPerGroup": number,
      "maxRestoreTabsTotal": number   // バックエンドの全体上限も採用
    }
  }
}
```

---

### 🔴 C-03: メッセージタイプの不一致

**問題:**
popup.jsからbackground.jsへ送信するメッセージタイプが異なります。

```javascript
// フロントエンド popup.js
chrome.runtime.sendMessage({ type: 'RESTORE_ALL_GROUPS' }, ...);

// フロントエンド background.js のリスナー
if (message.type === 'RESTORE_ALL_GROUPS') { ... }
if (message.type === 'RESTORE_GROUP') { ... }

// バックエンド background.js のリスナー
if (message.type === "MANUAL_RESTORE") { ... }  // ← 型名が違う
```

**影響:** フロントエンドpopupからバックエンドbackground.jsへのメッセージが無視され、手動復元・グループ別復元が動作しません。

**修正コード:**

```javascript
// 定数として定義し、両ファイルで共有する
// js/constants.js
export const MessageTypes = {
  RESTORE_ALL_GROUPS: 'RESTORE_ALL_GROUPS',
  RESTORE_GROUP: 'RESTORE_GROUP',
};

// background.js
import { MessageTypes } from './js/constants.js';

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === MessageTypes.RESTORE_ALL_GROUPS) { ... }
  if (message.type === MessageTypes.RESTORE_GROUP) { ... }
});
```

---

### 🔴 C-04: 自動分類モジュールの出力形式不一致

**問題:**

```javascript
// フロントエンド classifier.js
export function classifyTabs(tabs) {
  return [{ name: "GitHub", tabs: [...], reason: "3タブ" }];
  //       ^^^^ "name" プロパティ
}

// バックエンド classifier.js
function suggestClassification(tabs) {
  return [{ suggestedName: "開発・技術", tabs: [...] }];
  //       ^^^^^^^^^^^^^^ "suggestedName" プロパティ、reasonなし
}
```

**影響:** popup.jsがどちらのclassifierを使うかで、プロパティ名参照エラーが発生します。

```javascript
// フロントエンド popup.js は proposal.name を参照
proposals.forEach(proposal => {
  `📁 ${escapeHtml(proposal.name)}`  // バックエンドclassifierだとundefined
});

// バックエンド popup.js は suggestion.suggestedName を参照
label.textContent = suggestion.suggestedName;  // フロントエンドclassifierだとundefined
```

---

### 🔴 C-05: Service Workerでの `window` 参照エラー

**問題:**
バックエンドの`storage.js`はモジュールエクスポートに`window.StorageModule`を使用していますが、Service Worker（background.js）では`window`オブジェクトが存在しません。

```javascript
// バックエンド storage.js 末尾
window.StorageModule = { ... };  // ← Service Workerでは ReferenceError: window is not defined
```

**影響:** background.jsが`storage.js`を`<script>`で読み込もうとしても、Service Workerではスクリプトタグは使えません。バックエンドのbackground.jsはこの問題を認識し、ストレージアクセスコードを独自に重複実装していますが、以下のリスクがあります：

1. ストレージ操作ロジックが2箇所に重複（保守性低下）
2. バックエンドbackground.jsの`STORAGE_KEY`が`"groups"`だが、popup側は`window.StorageModule`経由で`"groups"`を使う—仮にpopup側だけ修正してキーを変えると即座に壊れる

**修正コード:**

```javascript
// ✅ ES Modulesで統一し、background.jsからimportする
// storage.js
export async function getAllGroups() { ... }

// background.js
import { getAllGroups } from './js/storage.js';  // type: module 必須
```

---

## セクション2: バグ・エッジケース不具合

### 🟠 H-01: 最後のタブを閉じるとウィンドウが消える

**場所:** フロントエンド `popup.js` → `handleCloseAllSavedTabs()`

**問題:**
グループの「全タブを閉じる」機能で、現在のウィンドウの全タブがグループURLと一致した場合、全タブが閉じられてウィンドウ自体が消えます。Chromeはウィンドウに最低1タブを要求するため、予期せぬ動作が発生します。

```javascript
// 現在の実装（危険）
const tabIdsToClose = openTabs
  .filter(t => t.url && groupUrls.has(t.url))
  .map(t => t.id);

chrome.tabs.remove(tabIdsToClose, ...);  // 全タブ閉じるとウィンドウも消える
```

**修正コード:**

```javascript
async function handleCloseAllSavedTabs(groupId) {
  const group = AppState.groups.find(g => g.id === groupId);
  if (!group || !group.tabs.length) {
    showToast('このグループにはタブがありません', 'info');
    return;
  }

  try {
    const openTabs = await new Promise((resolve) => {
      chrome.tabs.query({ currentWindow: true }, resolve);
    });

    const groupUrls = new Set(group.tabs.map(t => t.url));
    const tabIdsToClose = openTabs
      .filter(t => t.url && groupUrls.has(t.url))
      .map(t => t.id);

    if (tabIdsToClose.length === 0) {
      showToast('現在開いているタブと一致するものがありません', 'info');
      return;
    }

    // ★修正: 全タブを閉じてしまう場合は新しいタブを先に開く
    if (tabIdsToClose.length >= openTabs.length) {
      await new Promise((resolve) => {
        chrome.tabs.create({ url: 'chrome://newtab', active: true }, resolve);
      });
    }

    await new Promise((resolve, reject) => {
      chrome.tabs.remove(tabIdsToClose, () => {
        if (chrome.runtime.lastError) reject(new Error(chrome.runtime.lastError.message));
        else resolve();
      });
    });

    showToast(`${tabIdsToClose.length}タブを閉じました`, 'success');
  } catch (e) {
    showToast(`エラー: ${e.message}`, 'error');
  }
}
```

---

### 🟠 H-02: ストレージ読み書きの競合状態（Race Condition）

**場所:** 両実装の `storage.js` 全般

**問題:**
全ての書き込み操作が「全データ読み込み → 変更 → 全データ書き込み」のRead-Modify-Writeパターンです。ユーザーが高速にボタンを連打すると、以下のシーケンスでデータが消えます：

```
時刻 T1: 操作A - loadData() → groups = {g1, g2}
時刻 T2: 操作B - loadData() → groups = {g1, g2}  (まだAの保存前)
時刻 T3: 操作A - saveData({g1, g2, g3_new})  → g3追加
時刻 T4: 操作B - saveData({g1, g2_modified}) → g3がAの結果を上書きして消える
```

**修正コード（Mutex実装）:**

```javascript
// storage.js に追加
let _storageLock = Promise.resolve();

/**
 * ストレージ操作をシリアライズするMutex
 * @param {Function} fn - ストレージ操作を行う非同期関数
 * @returns {Promise<any>}
 */
export function withStorageLock(fn) {
  const prev = _storageLock;
  let releaseLock;
  _storageLock = new Promise((resolve) => { releaseLock = resolve; });

  return prev
    .then(() => fn())
    .finally(() => releaseLock());
}

// 使用例
export async function createGroup(name, color = '#4f8ef7') {
  return withStorageLock(async () => {
    const data = await loadData();
    const group = {
      id: generateId(),
      name: name.trim(),
      color,
      collapsed: false,
      restoreEnabled: true,
      createdAt: Date.now(),
      tabs: []
    };
    data.groups[group.id] = group;
    await saveData(data);
    return group;
  });
}
```

---

### 🟠 H-03: ID生成の衝突リスク

**場所:** 両実装の ID 生成関数

**問題:**

```javascript
// フロントエンド
function generateId() {
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 9)}`;
}

// バックエンド
function generateGroupId() {
  return `g-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}
```

`Date.now()` はミリ秒精度のため、`bulkCreateGroups()` で高速にループ実行すると同一タイムスタンプになる可能性があります。`Math.random()` の衝突確率は低いですが、暗号学的に安全ではありません。

**修正コード:**

```javascript
// crypto.randomUUID() を使用（Chrome 92+で利用可能）
function generateId() {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  // フォールバック: タイムスタンプ + 高ランダム性
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 9)}-${Math.random().toString(36).slice(2, 5)}`;
}
```

---

### 🟠 H-04: ポップアップ閉じによる非同期処理中断

**場所:** フロントエンド `popup.js` 全般

**問題:**
Chrome拡張機能のポップアップは、ユーザーがポップアップ外をクリックした瞬間に閉じられ、**実行中のJavaScriptが即座に中断**されます。以下のシナリオでデータ不整合が発生します：

1. ユーザーが「自動提案を適用」をクリック
2. `bulkCreateGroups()` が3グループ中2グループ目を保存中
3. ユーザーが誤ってポップアップ外をクリック
4. 3グループ目は保存されず、不完全な状態

**修正方針:**

```javascript
// 方法1: 重要な操作はbackground.jsに委譲する
async function handleApplyClassify() {
  try {
    // ポップアップが閉じても継続するようbackground.jsに処理を委譲
    const response = await chrome.runtime.sendMessage({
      type: 'APPLY_CLASSIFICATION',
      proposals: AppState.classifyProposals
    });
    if (response.success) {
      closeModal(DOM.modalClassify());
      await renderAll();
      showToast(`${response.groupCount}グループを作成しました`, 'success');
    }
  } catch (e) {
    showToast(`適用エラー: ${e.message}`, 'error');
  }
}

// background.js に追加
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === 'APPLY_CLASSIFICATION') {
    bulkCreateFromBackground(message.proposals)
      .then(count => sendResponse({ success: true, groupCount: count }))
      .catch(err => sendResponse({ success: false, error: err.message }));
    return true;
  }
});
```

---

### 🟠 H-05: `chrome://` タブ追加時のバリデーション不足

**場所:** フロントエンド `popup.js` → `handleAddCurrentTab()`

**問題:**

```javascript
// 現在の実装
if (!tabInfo.url || tabInfo.url.startsWith('chrome://')) {
  showToast('このタブは追加できません（chrome://ページ）', 'error');
  return;
}
```

`chrome-extension://`、`about:blank`、`edge://`、`data:` URIなどのブロック対象が不足しています。`tabManager.js`には`isRestorable()`関数が存在しますが、ここでは使われていません。

**修正コード:**

```javascript
import { isRestorable } from '../js/tabManager.js';

async function handleAddCurrentTab(groupId) {
  try {
    const tabInfo = await getCurrentTab();

    // ★修正: isRestorable()を使って一貫したバリデーション
    if (!tabInfo.url || !isRestorable(tabInfo.url)) {
      showToast('このタブは追加できません（内部ページ）', 'error');
      return;
    }

    await addTabToGroup(groupId, tabInfo);
    await renderAll();
    showToast(`「${tabInfo.title}」をグループに追加しました`, 'success');
  } catch (e) {
    showToast(e.message, 'error');
  }
}
```

---

### 🟠 H-06: バックエンド `emptyState` 要素のDOM脱落

**場所:** バックエンド `popup.js` → `renderGroups()`

**問題:**

```javascript
const emptyState = $("emptyState");  // 初期化時にDOM参照を取得

async function renderGroups() {
  groupList.innerHTML = "";  // ★ここで emptyState のDOM要素も破棄される

  if (groupArray.length === 0) {
    groupList.appendChild(emptyState);
    // ↑ emptyState の参照は残っているが、innerHTML=""で
    //   元のテキストノード等が破壊されている可能性
    emptyState.classList.remove("hidden");
  }
}
```

`innerHTML = ""` は子要素を全て破棄します。`emptyState` への参照は残りますが、2回目以降の`renderGroups()`呼び出しで再利用しようとすると、`emptyState`が既にDOMから切り離されている場合があります。

**修正コード:**

```javascript
async function renderGroups() {
  // ★修正: emptyState以外の子要素のみを削除
  Array.from(groupList.children).forEach(child => {
    if (child.id !== 'emptyState') {
      child.remove();
    }
  });

  if (groupArray.length === 0) {
    emptyState.classList.remove("hidden");
    return;
  }

  emptyState.classList.add("hidden");

  for (const group of groupArray) {
    const card = createGroupCard(group);
    groupList.insertBefore(card, emptyState);
  }
}
```

---

### 🟠 H-07: 復元時の重複タブ生成

**場所:** 両実装の `background.js` → `restoreAllGroups()`

**問題:**
Chrome再起動後、ユーザーが既にいくつかのタブを手動で開いている場合、復元処理が同じURLのタブを重複して開きます。また、手動復元ボタンを複数回押すと、タブが倍々に増えます。

**修正コード:**

```javascript
async function restoreAllGroups(trigger) {
  const data = await loadData();
  const { groups, settings } = data;

  if (trigger === 'startup' && !settings.autoRestoreOnStartup) {
    return { totalOpened: 0, totalSkipped: 0, groupCount: 0 };
  }

  // ★修正: 現在開いているタブのURLを取得して重複を回避
  const existingTabs = await new Promise((resolve) => {
    chrome.tabs.query({}, (tabs) => resolve(tabs));
  });
  const existingUrls = new Set(existingTabs.map(t => t.url).filter(Boolean));

  const groupList = Object.values(groups).sort((a, b) => a.createdAt - b.createdAt);
  let totalOpened = 0;
  let totalSkipped = 0;

  for (const group of groupList) {
    if (!group.tabs || group.tabs.length === 0) continue;
    if (group.restoreEnabled === false) continue;  // グループ別復元フラグ

    const restorableTabs = group.tabs
      .filter(t => isRestorable(t.url))
      .filter(t => !existingUrls.has(t.url));  // ★既に開いているURLは除外

    const { opened, skipped } = await openTabsBatch(
      restorableTabs,
      settings.maxRestoreTabsPerGroup
    );

    // 開いたURLを追跡して次のグループとの重複も防止
    restorableTabs.slice(0, opened).forEach(t => existingUrls.add(t.url));

    totalOpened += opened;
    totalSkipped += skipped;
  }

  return { totalOpened, totalSkipped, groupCount: groupList.length };
}
```

---

### 🟠 H-08: `handleOpenAllTabs` のtab上限がハードコード

**場所:** フロントエンド `popup.js`

**問題:**

```javascript
async function handleOpenAllTabs(groupId) {
  const { opened, skipped } = await openTabsBatch(group.tabs, 20);  // ★ハードコード
}
```

`settings.maxRestoreTabsPerGroup` の値を使うべきですが、ハードコードの`20`になっています。

**修正コード:**

```javascript
async function handleOpenAllTabs(groupId) {
  const group = AppState.groups.find(g => g.id === groupId);
  if (!group || !group.tabs.length) {
    showToast('このグループにはタブがありません', 'info');
    return;
  }

  try {
    // ★修正: 設定値を参照
    const data = await loadData();
    const maxTabs = data.settings.maxRestoreTabsPerGroup;

    showToast('タブを開いています...', 'info');
    const { opened, skipped } = await openTabsBatch(group.tabs, maxTabs);
    // ...
  }
}
```

---

### 🟠 H-09: バックエンド `editBtn.onclick` 上書きによるメモリリーク

**場所:** バックエンド `popup.js` → `startEditGroupName()`

**問題:**

```javascript
function startEditGroupName(groupId, nameEl, editBtn) {
  // ...
  editBtn.onclick = (e) => {  // ★onclickを直接上書き→古いリスナーは残る場合あり
    e.stopPropagation();
    save();
  };
}
```

`addEventListener`で登録した元のクリックリスナーは`onclick`上書きでは削除されません。ユーザーが編集→キャンセル→編集を繰り返すと、古い`save()`クロージャが残り続けます。

**修正コード:**

```javascript
function startEditGroupName(groupId, nameEl, editBtn) {
  const input = document.createElement("input");
  input.className = "group-name-input";
  input.type = "text";
  input.value = nameEl.textContent;
  input.maxLength = 50;

  nameEl.replaceWith(input);
  input.focus();
  input.select();

  // ★修正: 新しいボタンに差し替えてリスナー汚染を防止
  const saveBtn = editBtn.cloneNode(true);
  saveBtn.textContent = "💾";
  saveBtn.title = "保存";
  editBtn.replaceWith(saveBtn);

  const save = async () => {
    const newName = input.value.trim();
    if (!newName) {
      showMessage("グループ名を入力してください", "warn");
      input.focus();
      return;
    }
    try {
      await Storage.updateGroupName(groupId, newName);
      showMessage(`グループ名を "${newName}" に変更しました`, "info");
      await renderGroups();  // 全再描画で元のDOMに戻る
    } catch (err) {
      showMessage(`エラー: ${err.message}`, "error", 0);
    }
  };

  saveBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    save();
  });

  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter") save();
    if (e.key === "Escape") renderGroups();
  });

  // フォーカスアウトでもキャンセルとして処理
  input.addEventListener("blur", () => {
    setTimeout(() => renderGroups(), 100);
  });
}
```

---

## セクション3: セキュリティ脆弱性

### 🟡 S-01: `javascript:` URL インジェクション

**場所:** 両実装のタブ開く処理

**問題:**
ストレージに保存されたURLが`javascript:`プロトコルの場合、`chrome.tabs.create({ url })` で任意のJavaScriptが実行される可能性があります。

```javascript
// フロントエンド popup.js
el.addEventListener('click', (e) => {
  chrome.tabs.create({ url: el.dataset.url, active: true });
  // ↑ el.dataset.url が "javascript:alert(1)" だった場合→XSS
});

// バックエンド popup.js
titleEl.addEventListener("click", (e) => {
  chrome.tabs.create({ url: tab.url, active: true });
});
```

**攻撃シナリオ:** 
1. ユーザーがブックマークレット（`javascript:`URL）のタブを開いた状態で「現在のタブを追加」
2. ストレージに`javascript:`URLが保存される
3. 他のタイミングでそのタブ項目をクリック→任意コード実行

**修正コード:**

```javascript
// tabManager.js に追加
export function isSafeUrl(url) {
  if (!url) return false;
  try {
    const parsed = new URL(url);
    const allowedProtocols = ['http:', 'https:', 'ftp:'];
    return allowedProtocols.includes(parsed.protocol);
  } catch {
    return false;
  }
}

// popup.js でのタブ開く処理
import { isSafeUrl } from '../js/tabManager.js';

el.addEventListener('click', (e) => {
  const url = el.dataset.url;
  if (isSafeUrl(url)) {
    chrome.tabs.create({ url, active: true });
  } else {
    showToast('安全でないURLのため開けません', 'error');
  }
});

// storage.js でのタブ追加時にもバリデーション追加
export async function addTabToGroup(groupId, tabInfo) {
  if (!isSafeUrl(tabInfo.url)) {
    throw new Error('このURLは保存できません（安全でないプロトコル）');
  }
  // ...
}
```

---

### 🟡 S-02: `updateGroup` の任意フィールド上書き

**場所:** フロントエンド `storage.js` → `updateGroup()`

**問題:**

```javascript
export async function updateGroup(groupId, updates) {
  const data = await loadData();
  data.groups[groupId] = { ...data.groups[groupId], ...updates };
  // ↑ updates に { id: "別のID" } や { tabs: [] } が含まれると
  //   データ整合性が壊れる
  await saveData(data);
}
```

**修正コード:**

```javascript
export async function updateGroup(groupId, updates) {
  const data = await loadData();
  if (!data.groups[groupId]) {
    throw new Error(`Group not found: ${groupId}`);
  }

  // ★修正: 更新可能なフィールドをホワイトリストで制限
  const allowedFields = ['name', 'color', 'collapsed', 'restoreEnabled'];
  const safeUpdates = {};

  for (const key of allowedFields) {
    if (key in updates) {
      safeUpdates[key] = updates[key];
    }
  }

  // バリデーション
  if ('name' in safeUpdates && (!safeUpdates.name || typeof safeUpdates.name !== 'string')) {
    throw new Error('グループ名は空にできません');
  }

  data.groups[groupId] = { ...data.groups[groupId], ...safeUpdates };
  await saveData(data);
  return data.groups[groupId];
}
```

---

### 🟡 S-03: faviconURLによる追跡リスク

**場所:** フロントエンド `popup.js` → `createTabItemHTML()`

**問題:**

```javascript
function createTabItemHTML(tab) {
  const faviconHTML = tab.favicon
    ? `<img class="tab-favicon" src="${escapeHtml(tab.favicon)}" ...>`
    : `...`;
}
```

外部サイトのfavicon URLをそのまま`<img src>`に設定しているため、ポップアップを開くたびに外部サーバーへリクエストが発生します。悪意あるfavicon URLはトラッキングやタイミング攻撃に利用される可能性があります。

**修正コード:**

```javascript
function createTabItemHTML(tab) {
  // ★修正: chrome://favicon/ APIを使用してChromeキャッシュから取得
  // または、保存時にfaviconをBase64変換して保存する
  const faviconUrl = tab.favicon
    ? `chrome-extension://${chrome.runtime.id}/_favicon/?pageUrl=${encodeURIComponent(tab.url)}&size=16`
    : '';

  // 注意: _favicon APIを使うには manifest.json に以下を追加:
  // "permissions": ["favicon"]
  // Chrome 128+で利用可能

  // フォールバック: 外部URLをそのまま使う場合はCSPヘッダーで制限
  const faviconHTML = faviconUrl
    ? `<img class="tab-favicon" src="${escapeHtml(faviconUrl)}" alt="" onerror="this.style.display='none'">`
    : `<span class="tab-favicon--placeholder">🔗</span>`;

  return `...`;
}
```

---

### 🟡 S-04: `onerror` ハンドラのインラインイベント

**場所:** フロントエンド `popup.js` → `createTabItemHTML()`

**問題:**

```html
<img ... onerror="this.style.display='none'">
```

Manifest V3のContent Security Policy (CSP) は、デフォルトでインラインイベントハンドラを禁止しています。この`onerror`は実行時にCSP違反エラーを出す可能性があります。

**修正コード:**

```javascript
function createGroupCard(group) {
  // ...
  card.innerHTML = `...`;  // onerror属性を削除

  // ★修正: DOMに挿入後にイベントリスナーをプログラム的に追加
  card.querySelectorAll('.tab-favicon').forEach(img => {
    img.addEventListener('error', () => {
      img.style.display = 'none';
      // フォールバックアイコンを表示
      const placeholder = document.createElement('span');
      placeholder.className = 'tab-favicon--placeholder';
      placeholder.textContent = '🔗';
      img.replaceWith(placeholder);
    });
  });
}
```

---

## セクション4: 設計上の懸念・改善推奨

### 🔵 D-01: 自動分類アルゴリズムの重複と一貫性

**問題:**
フロントエンドとバックエンドで分類ロジックが完全に異なります。

| 観点 | フロントエンド `classifier.js` | バックエンド `classifier.js` |
|---|---|---|
| 分類単位 | ドメイン → サブキーワード | カテゴリルール → ドメインフォールバック |
| 「その他」条件 | ドメイン内1タブ以下 | ルール外 & ドメイン内1タブ |
| サブ分類 | タイトルキーワードで分割 | なし |
| 入力型 | `{url, title, favicon}` | `chrome.tabs.Tab` |
| 出力型 | `{name, tabs, reason}` | `{suggestedName, tabs}` |

**推奨:**
フロントエンド版のほうが機能が豊富（サブ分類あり）ですが、バックエンド版のカテゴリルールベースも良い設計です。両方の長所を統合した実装を推奨します。

---

### 🔵 D-02: ストレージ容量超過の検知不足

**問題:**
計画書のリスクに「5MB超過時はエラー通知を実装」とありますが、実装では`saveData`のエラーキャッチのみで、事前の容量チェックがありません。

**修正コード:**

```javascript
export async function saveData(data) {
  return new Promise((resolve, reject) => {
    chrome.storage.local.set({ [STORAGE_KEY]: data }, () => {
      if (chrome.runtime.lastError) {
        const errMsg = chrome.runtime.lastError.message;
        if (errMsg.includes('QUOTA_BYTES')) {
          reject(new Error('ストレージ容量の上限（5MB）に達しました。不要なグループを削除してください。'));
        } else {
          reject(new Error(errMsg));
        }
      } else {
        resolve();
      }
    });
  });
}

// 容量の事前チェック関数
export async function checkStorageUsage() {
  return new Promise((resolve) => {
    chrome.storage.local.getBytesInUse(null, (bytes) => {
      const maxBytes = 5 * 1024 * 1024; // 5MB
      resolve({
        usedBytes: bytes,
        maxBytes,
        usagePercent: ((bytes / maxBytes) * 100).toFixed(1),
        isWarning: bytes > maxBytes * 0.8,  // 80%超過で警告
        isCritical: bytes > maxBytes * 0.95  // 95%超過で危険
      });
    });
  });
}
```

---

### 🔵 D-03: `onInstalled` の `update` 時のデータマイグレーション未実装

**場所:** フロントエンド `background.js`

**問題:**

```javascript
chrome.runtime.onInstalled.addListener(async (details) => {
  if (details.reason === 'update') {
    console.log(`[TabGroupManager] 更新完了`);
    // ← スキーマ変更時のデータマイグレーションが無い
  }
});
```

将来スキーマを変更（例: `restoreEnabled`フィールドの追加）した場合、既存データとの互換性が壊れます。

**修正コード:**

```javascript
chrome.runtime.onInstalled.addListener(async (details) => {
  if (details.reason === 'install') {
    await initializeStorage();
  } else if (details.reason === 'update') {
    await migrateStorage(details.previousVersion);
  }
});

async function migrateStorage(fromVersion) {
  const data = await loadData();

  // v1.0.0 → v1.1.0: restoreEnabled フィールド追加
  for (const group of Object.values(data.groups)) {
    if (group.restoreEnabled === undefined) {
      group.restoreEnabled = true;
    }
    if (group.collapsed === undefined) {
      group.collapsed = false;
    }
  }

  // settings のデフォルト値補完
  data.settings = {
    ...getDefaultSettings(),
    ...data.settings
  };

  await saveData(data);
  console.log(`[TabGroupManager] マイグレーション完了: v${fromVersion} → v${chrome.runtime.getManifest().version}`);
}
```

---

### 🔵 D-04: バックエンドの復元で `maxRestoreTabsTotal` が存在するがフロントエンドにない

**問題:**
バックエンドのbackground.jsには `MAX_RESTORE_TABS_TOTAL = 50` の全体上限がありますが、フロントエンドにはこの安全弁がありません。

```javascript
// バックエンド（安全）
const MAX_RESTORE_TABS_TOTAL = 50;
if (totalRestoredCount >= MAX_RESTORE_TABS_TOTAL) {
  console.warn('Total restore limit reached.');
  break;
}

// フロントエンド（上限なし→グループ数×20タブが無制限に開く）
for (const group of groupList) {
  await openTabsBatch(restorableTabs, settings.maxRestoreTabsPerGroup);
  // ★ 全体上限チェックがない
}
```

**修正:** バックエンドの `maxRestoreTabsTotal` をフロントエンドにも統合してください。

---

### 🔵 D-05: popup.css の重複（2つの完全に異なるCSS）

**問題:**
フロントエンドはダークテーマ（`#1a1a2e`ベース）、バックエンドはライトテーマ（`#f5f7fa`ベース）です。ポップアップ幅もフロントエンド380px、バックエンド420pxで異なります。HTML構造も完全に異なるため、CSSの互換性はゼロです。

**推奨:** どちらかのデザインを選択して統一してください。

---

### 🔵 D-06: `confirm()` のUX問題

**場所:** フロントエンド `popup.js` → `handleDeleteGroup()`

**問題:**

```javascript
const confirmed = window.confirm(`グループ「${group.name}」を削除しますか？`);
```

Chrome拡張機能のポップアップ内で`confirm()`を呼ぶと、ポップアップとは別のダイアログが表示されます。このダイアログが表示されるとポップアップが閉じてしまうブラウザバージョンがあります。

**修正方針:** カスタムの確認モーダルを使用する。

```javascript
// ★修正: 削除確認モーダルを追加
async function handleDeleteGroup(groupId) {
  const group = AppState.groups.find(g => g.id === groupId);
  if (!group) return;

  // カスタム確認UIを表示
  return new Promise((resolve) => {
    showConfirmModal(
      `グループ「${group.name}」を削除しますか？`,
      'タブのURLは消えますが、ブラウザで開いているタブには影響しません。',
      async () => {
        try {
          await deleteGroup(groupId);
          await renderAll();
          showToast(`グループ「${group.name}」を削除しました`, 'info');
        } catch (e) {
          showToast(`削除エラー: ${e.message}`, 'error');
        }
        resolve();
      },
      () => resolve()
    );
  });
}
```

---

## セクション5: 統合修正チェックリスト

以下の順序で修正を実施することを推奨します：

| 優先度 | ID | 修正項目 | 作業量 |
|---|---|---|---|
| 1 | C-01 | ES Modulesにモジュールシステムを統一 | 大 |
| 2 | C-02 | ストレージキー・スキーマの統一 | 大 |
| 3 | C-03 | メッセージタイプの統一定数化 | 小 |
| 4 | C-04 | classifier出力形式の統一 | 中 |
| 5 | C-05 | Service Worker対応（window除去） | 中 |
| 6 | S-01 | javascript: URLブロック | 小 |
| 7 | S-02 | updateGroupのホワイトリスト化 | 小 |
| 8 | H-01 | 最後のタブ保護 | 小 |
| 9 | H-02 | ストレージMutex実装 | 中 |
| 10 | H-07 | 復元時の重複タブ防止 | 中 |
| 11 | S-04 | インラインイベントハンドラ除去 | 小 |
| 12 | H-05 | URL バリデーション統一 | 小 |
| 13 | D-03 | データマイグレーション実装 | 中 |
| 14 | H-04 | 重要操作のbackground委譲 | 大 |
| 15 | D-04 | 復元タブ全体上限の追加 | 小 |

---

## 付録: 統一版manifest.json（推奨）

```json
{
  "manifest_version": 3,
  "name": "TabGroup Manager",
  "version": "1.0.0",
  "description": "タブをユーザー定義グループで管理し、再起動後も自動復元できるChrome拡張機能",

  "permissions": [
    "tabs",
    "storage"
  ],

  "action": {
    "default_popup": "popup/popup.html",
    "default_icon": {
      "16":  "icons/icon16.png",
      "48":  "icons/icon48.png",
      "128": "icons/icon128.png"
    },
    "default_title": "TabGroup Manager"
  },

  "background": {
    "service_worker": "background.js",
    "type": "module"
  },

  "icons": {
    "16":  "icons/icon16.png",
    "48":  "icons/icon48.png",
    "128": "icons/icon128.png"
  }
}
```

以上が検証報告書です。**最優先でセクション1（C-01〜C-05）の致命的不整合を解消**し、その後セクション3のセキュリティ修正、セクション2のバグ修正の順に対応することを推奨します。

---

## 🏆 最終総括
# 納品用最終レポート
## Chrome拡張機能「TabGroup Manager」

---

> **文書情報**
> | 項目 | 内容 |
> |---|---|
> | プロジェクト名 | TabGroup Manager（Chrome拡張機能） |
> | 文書種別 | 納品用最終レポート |
> | ステータス | **条件付き承認 ― 要修正後リリース可** |
> | 作成者 | 統括マネージャー |
> | 対象読者 | 開発者・将来の自分 |

---

## 目次

1. [エグゼクティブサマリー](#1)
2. [確定仕様](#2)
3. [成果物の構成と完成状態](#3)
4. [QA検証結果サマリー](#4)
5. [修正実施計画（優先順位付き）](#5)
6. [今後の運用方針](#6)
7. [承認状況と次のアクション](#7)

---

<a id="1"></a>
## 1. エグゼクティブサマリー

### 1.1 プロジェクト概要

Chrome再起動後もタブグループを永続化・自動復元できる個人用Chrome拡張機能の開発プロジェクト。Manifest V3 / Vanilla JS / chrome.storage.local を技術基盤とし、フレームワーク・外部依存ゼロの構成で設計・実装した。

### 1.2 現時点の総合評価

```
┌──────────────────────────────────────────────────────────┐
│  判定: ⚠️ 条件付き承認                                    │
│                                                          │
│  フロントエンド実装・バックエンド実装それぞれは           │
│  単体として完成度が高い。                                 │
│  ただし両者を結合するための整合修正が完了するまで         │
│  本番利用（Chrome へのロード）は推奨しない。              │
└──────────────────────────────────────────────────────────┘
```

### 1.3 解決すべき問題の規模感

| 重大度 | 件数 | リリースブロッカー |
|---|---|---|
| 🔴 Critical（動作不能） | 5件 | **Yes** |
| 🟠 High（バグ・エッジケース） | 9件 | **Yes（主要7件）** |
| 🟡 Medium（セキュリティ） | 4件 | **Yes（S-01のみ）** |
| 🔵 Low（設計改善） | 6件 | No |

**Criticalの5件と、High・Mediumの最重要項目を修正すれば、計画書の受け入れ条件7項目を全て充足できる状態になる。**

---

<a id="2"></a>
## 2. 確定仕様

### 2.1 機能仕様（確定版）

計画書の必須要件に対し、QA検証・実装内容を照合した上で以下を確定仕様とする。

#### ✅ 確定・実装完了

| # | 機能 | 確定仕様 | 実装確認 |
|---|---|---|---|
| F-01 | グループ作成 | 名前・カラーを指定して新規作成 | ✅ |
| F-02 | タブ追加 | 現在のアクティブタブをグループに追加。`http:`/`https:`のみ保存可 | ✅（要バリデーション修正） |
| F-03 | タブ削除 | グループからタブ情報を削除（ブラウザで開いているタブには影響しない） | ✅ |
| F-04 | グループ名編集 | インラインエディットで即時更新 | ✅（要リスナー修正） |
| F-05 | グループ削除 | グループとタブ情報を削除（ブラウザには影響しない） | ✅（要確認モーダル修正） |
| F-06 | 自動分類提案 | ドメイン・タイトルキーワードを元に提案を表示。提案ボタン押下時のみ動作 | ✅（要出力形式統一） |
| F-07 | 自動復元 | Chrome起動時、`autoRestoreOnStartup=true` のとき保存グループのタブを自動で開く | ✅（要重複防止修正） |
| F-08 | 手動復元 | ポップアップから手動でグループのタブを開くことができる | ✅ |
| F-09 | 一括タブ操作 | グループ単位でタブを一括で開く・閉じる | ✅（要最後のタブ保護） |

#### 📝 仕様追加確定（QA指摘を受けて計画書から拡張）

| # | 項目 | 確定内容 | 追加理由 |
|---|---|---|---|
| F-10 | グループ別復元フラグ | `restoreEnabled` フィールドでグループごとに復元ON/OFFを切り替え可能 | 計画書の未確定事項を解決。バックエンド実装の良設計を採用 |
| F-11 | 復元タブ数上限 | グループ別: 20タブ / 全体: 50タブ を上限とする | バックエンド実装の安全弁をフロントエンドにも統合 |
| F-12 | 重複タブ防止 | 復元時、既に同URLのタブが開いていれば再度開かない | H-07の修正を仕様として確定 |
| F-13 | URL安全性チェック | `javascript:` / `chrome://` / `chrome-extension://` / `about:` / `data:` は保存・開く操作を拒否 | S-01, H-05の修正を仕様として確定 |

### 2.2 非機能仕様（確定版）

| 項目 | 確定内容 |
|---|---|
| 対象ブラウザ | Chrome 92以上（`crypto.randomUUID()` 要件） |
| ストレージ | chrome.storage.local / 5MB上限 / 80%超過で警告通知 |
| タブ数想定 | 100タブ以下 |
| モジュール方式 | ES Modules で統一（`type: "module"`） |
| manifest_version | 3 |
| パーミッション | `tabs`, `storage` のみ |
| デバイス間同期 | 非対応（chrome.storage.sync は使用しない） |
| ビルドツール | 不要（Vanilla JS） |

### 2.3 確定スキーマ（ストレージ定義）

QA指摘C-02を受け、フロントエンド・バックエンドの差異を統合した最終スキーマを以下に確定する。

```json
{
  "tabGroupManager": {
    "groups": {
      "<groupId: string(UUID)>": {
        "id":             "string   // crypto.randomUUID()",
        "name":           "string   // 50文字以内",
        "color":          "string   // 例: '#4f8ef7'",
        "collapsed":      "boolean  // UIの折りたたみ状態",
        "restoreEnabled": "boolean  // グループ別自動復元フラグ",
        "createdAt":      "number   // Unix timestamp (ms)",
        "tabs": [
          {
            "id":      "string  // crypto.randomUUID()",
            "url":     "string  // http/https のみ",
            "title":   "string",
            "favicon": "string  // URL or ''",
            "addedAt": "number"
          }
        ]
      }
    },
    "settings": {
      "autoRestoreOnStartup":      "boolean // デフォルト: true",
      "maxRestoreTabsPerGroup":    "number  // デフォルト: 20",
      "maxRestoreTabsTotal":       "number  // デフォルト: 50"
    }
  }
}
```

### 2.4 確定メッセージ型（popup ⇔ background 間）

QA指摘C-03を受け、`js/constants.js` で一元管理することを確定する。

```javascript
// js/constants.js（新規追加ファイル）
export const MessageTypes = {
  RESTORE_ALL_GROUPS:   'RESTORE_ALL_GROUPS',
  RESTORE_GROUP:        'RESTORE_GROUP',
  APPLY_CLASSIFICATION: 'APPLY_CLASSIFICATION',
};
```

---

<a id="3"></a>
## 3. 成果物の構成と完成状態

### 3.1 ディレクトリ構成（確定版）

```
tabgroup-manager/
├── manifest.json              ✅ 確定（下記参照）
├── background.js              ⚠️ 修正必要（C-01, C-02, C-05, H-07対応）
├── popup/
│   ├── popup.html             ⚠️ 修正必要（D-05: CSS/HTMLテーマ統一）
│   ├── popup.js               ⚠️ 修正必要（H-01, H-04, H-05, S-04, D-06対応）
│   └── popup.css              ⚠️ 修正必要（D-05: テーマ統一）
├── js/
│   ├── constants.js           🆕 新規作成（C-03対応）
│   ├── storage.js             ⚠️ 修正必要（C-01, C-02, H-02, S-02対応）
│   ├── tabManager.js          ⚠️ 修正必要（H-05, S-01対応）
│   └── classifier.js          ⚠️ 修正必要（C-04対応）
└── icons/
    ├── icon16.png             ✅
    ├── icon48.png             ✅
    └── icon128.png            ✅
```

### 3.2 確定 manifest.json

```json
{
  "manifest_version": 3,
  "name": "TabGroup Manager",
  "version": "1.0.0",
  "description": "タブをユーザー定義グループで管理し、再起動後も自動復元できるChrome拡張機能",

  "permissions": [
    "tabs",
    "storage"
  ],

  "action": {
    "default_popup": "popup/popup.html",
    "default_icon": {
      "16":  "icons/icon16.png",
      "48":  "icons/icon48.png",
      "128": "icons/icon128.png"
    },
    "default_title": "TabGroup Manager"
  },

  "background": {
    "service_worker": "background.js",
    "type": "module"
  },

  "icons": {
    "16":  "icons/icon16.png",
    "48":  "icons/icon48.png",
    "128": "icons/icon128.png"
  }
}
```

> **設計判断メモ:** `favicon` パーミッションは「追跡リスク vs UX」のトレードオフ検討の結果、**v1.0.0では追加しない**。favicon表示は `chrome://favicon/`API経由ではなく、保存済みURLのみ表示するシンプルな実装に留める。

### 3.3 ファイル別完成度

| ファイル | 完成度 | 主な残課題 |
|---|---|---|
| manifest.json | **100%** | なし |
| constants.js | **0%**（新規） | 新規作成が必要（小作業） |
| storage.js | **65%** | スキーマ統一・Mutex実装・ホワイトリスト化 |
| tabManager.js | **75%** | URL安全性チェックの統一 |
| classifier.js | **60%** | 出力形式の統一（name / reason フィールド確定） |
| background.js | **70%** | ESM統一・重複タブ防止・全体上限追加 |
| popup.html | **80%** | テーマ統一・confirm()モーダル化 |
| popup.js | **70%** | インラインイベント除去・ポップアップ中断対策・URL検証統一 |
| popup.css | **80%** | テーマ統一のみ |

---

<a id="4"></a>
## 4. QA検証結果サマリー

### 4.1 受け入れ条件7項目の合否

| # | 受け入れ条件 | 現状判定 | ブロック理由 |
|---|---|---|---|
| AC-01 | グループを新規作成し任意の名前をつけられること | ✅ 合格 | — |
| AC-02 | 現在開いているタブをグループに追加できること | ⚠️ 条件付き | H-05: URL検証が不完全 |
| AC-03 | グループからタブを削除できること | ✅ 合格 | — |
| AC-04 | グループ名を編集できること | ⚠️ 条件付き | H-09: リスナー重複リーク |
| AC-05 | グループを削除できること | ⚠️ 条件付き | D-06: confirm()でポップアップが閉じる可能性 |
| AC-06 | 自動分類提案ボタンでドメイン単位のグループ案が表示されること | ❌ 不合格 | C-04: 出力形式不一致でundefined表示 |
| AC-07 | Chrome再起動後に保存済みグループのタブが自動復元されること | ❌ 不合格 | C-01/C-02/C-05: モジュール・スキーマ不整合で復元ゼロ |

**現在の合格率: 2/7（29%） → 修正完了後: 7/7（100%）見込み**

### 4.2 Critical問題5件の概要と判定

| ID | 問題 | 影響範囲 | マネージャー判定 |
|---|---|---|---|
| C-01 | ESM vs グローバル名前空間の混在 | 全機能停止 | **即時修正必須** |
| C-02 | ストレージキー・スキーマ不一致 | 復元機能ゼロ | **即時修正必須** |
| C-03 | メッセージタイプ名不一致 | 手動復元・グループ別復元ゼロ | **即時修正必須** |
| C-04 | classifier出力形式不一致 | 自動分類表示崩壊 | **即時修正必須** |
| C-05 | Service Workerでwindow参照エラー | background.js起動失敗 | **C-01修正で同時解決** |

### 4.3 High問題9件の優先判定

| ID | 問題 | リリースブロッカー | 判定理由 |
|---|---|---|---|
| H-01 | 全タブ閉じてウィンドウ消滅 | **Yes** | UXクリティカル・再現性高 |
| H-02 | ストレージ競合（Race Condition） | No（v1.0は低頻度）| 個人利用・低頻度のため v1.1で対応 |
| H-03 | ID生成衝突リスク | No（確率的に無視可） | `crypto.randomUUID()`採用で解決済み |
| H-04 | ポップアップ閉じによる処理中断 | **Yes** | 自動分類適用の確実性に影響 |
| H-05 | URL検証不足 | **Yes** | 保存データの整合性に影響 |
| H-06 | emptyState DOM脱落 | **Yes** | グループ削除後にUIが壊れる |
| H-07 | 復元時重複タブ生成 | **Yes** | 手動復元の多重実行で顕在化 |
| H-08 | タブ上限ハードコード | No | 設定値と乖離するが動作はする |
| H-09 | onclick上書きによるリスナーリーク | **Yes** | 編集繰り返しで動作が壊れる |

### 4.4 セキュリティ・設計問題の判定

| ID | 問題 | 判定 |
|---|---|---|
| S-01 | `javascript:` URL実行 | **リリースブロッカー** |
| S-02 | updateGroupの任意フィールド書き込み | v1.0 対応推奨（個人利用なので許容範囲内だが修正コスト小） |
| S-03 | faviconによる追跡リスク | v1.1 以降で対応（個人利用のためリスク限定的） |
| S-04 | インラインイベントハンドラのCSP違反 | **リリースブロッカー**（CSPエラーで機能停止の可能性） |
| D-01〜D-06 | 設計改善 | すべて v1.1 以降で対応 |

---

<a id="5"></a>
## 5. 修正実施計画（優先順位付き）

### フェーズ1: リリースブロッカー修正（v1.0.0リリース前 必須）

**想定作業時間: 4〜6時間**

---

#### Step 1-A: モジュール統一基盤（C-01・C-05 同時解決）

**作業内容:** 全ファイルをES Modules方式に統一する。

```javascript
// ❌ 修正前: storage.js 末尾（window使用）
window.StorageModule = { getAllGroups, createGroup, ... };

// ✅ 修正後: storage.js
export { getAllGroups, createGroup, addTabToGroup, ... };
```

```javascript
// ✅ 修正後: background.js 先頭
import { loadData, saveData } from './js/storage.js';
import { MessageTypes } from './js/constants.js';
import { isRestorable } from './js/tabManager.js';
```

```html
<!-- ✅ 修正後: popup.html -->
<script type="module" src="popup.js"></script>
```

**完了条件:** `chrome.extension.getBackgroundPage()` で undefined エラーが出ず、background.js が正常起動すること。

---

#### Step 1-B: ストレージスキーマ統一（C-02 解決）

**作業内容:** 全ファイルのストレージキーとデータ構造を「確定スキーマ（セクション2.3）」に統一する。

```javascript
// js/storage.js: キーを統一
const STORAGE_KEY = 'tabGroupManager';

// デフォルト値関数を定義し initializeStorage / migrateStorage から呼び出す
function getDefaultData() {
  return {
    groups: {},
    settings: {
      autoRestoreOnStartup: true,
      maxRestoreTabsPerGroup: 20,
      maxRestoreTabsTotal: 50,
    }
  };
}
```

**完了条件:** popup.js で保存したデータを background.js が同一キーで読み出せること。DevTools → Application → Storage で確認。

---

#### Step 1-C: 定数ファイル作成とメッセージ統一（C-03 解決）

**作業内容:** `js/constants.js` を新規作成し、popup.js・background.js の両方でインポートする。

```javascript
// js/constants.js（新規作成）
export const STORAGE_KEY = 'tabGroupManager';

export const MessageTypes = {
  RESTORE_ALL_GROUPS:   'RESTORE_ALL_GROUPS',
  RESTORE_GROUP:        'RESTORE_GROUP',
  APPLY_CLASSIFICATION: 'APPLY_CLASSIFICATION',
};
```

**完了条件:** popup → background への `RESTORE_ALL_GROUPS` メッセージがbackground.jsのonMessageで受信できること。

---

#### Step 1-D: Classifier出力形式統一（C-04 解決）

**作業内容:** classifier.js の返却型を以下に統一する。フロントエンド版のロジック（サブ分類あり）をベースに、バックエンド版のカテゴリルールを統合する。

```javascript
// js/classifier.js（確定インターフェース）
export function classifyTabs(tabs) {
  // 返却型（確定）:
  return [
    {
      name:   "string  // グループ名の提案",
      tabs:   "Tab[]   // このグループに入るタブの配列",
      reason: "string  // 提案理由の説明文（例: 'ドメイン: github.com, 3タブ'）",
    }
  ];
}
```

**完了条件:** popup.js の `proposal.name` 参照でundefinedが出ないこと。

---

#### Step 1-E: URL安全性チェック統一（S-01・H-05 同時解決）

**作業内容:** `tabManager.js` に `isSafeUrl()` を定義し、タブ追加・タブ表示クリック・storage保存の全箇所で使用する。

```javascript
// js/tabManager.js
export function isSafeUrl(url) {
  if (!url || typeof url !== 'string') return false;
  try {
    const parsed = new URL(url);
    return ['http:', 'https:'].includes(parsed.protocol);
  } catch {
    return false;
  }
}

export function isRestorable(url) {
  return isSafeUrl(url);
}
```

**完了条件:** `javascript:alert(1)` のURLがストレージに保存されず、保存済みであっても開けないこと。

---

#### Step 1-F: インラインイベントハンドラ除去（S-04 解決）

**作業内容:** popup.js の全 `innerHTML` 生成コードから `onerror=`, `onclick=` などのインライン属性を除去し、`addEventListener` に置き換える。

```javascript
// ❌ 修正前
img.outerHTML = `<img src="${favicon}" onerror="this.style.display='none'">`;

// ✅ 修正後
const img = document.createElement('img');
img.src = favicon;
img.addEventListener('error', () => { img.style.display = 'none'; });
```

**完了条件:** DevTools コンソールに CSP violation エラーが出ないこと。

---

#### Step 1-G: UIバグ修正3点（H-01・H-06・H-09 解決）

各修正は独立しているため並行作業可能。

**H-01: 最後のタブ保護**（popup.js の `handleCloseAllSavedTabs`）
```javascript
// タブを全て閉じる前に、閉じるタブ数 >= 全タブ数 なら先に新規タブを開く
if (tabIdsToClose.length >= openTabs.length) {
  await chrome.tabs.create({ url: 'chrome://newtab', active: true });
}
```

**H-06: emptyState DOM保護**（popup.js の `renderGroups`）
```javascript
// innerHTML = "" の代わりに emptyState 以外の子要素だけ削除
Array.from(groupList.children).forEach(child => {
  if (child.id !== 'emptyState') child.remove();
});
```

**H-09: リスナーリーク防止**（popup.js の `startEditGroupName`）
```javascript
// editBtn を cloneNode() で差し替え、古いリスナーを物理的に切断する
const saveBtn = editBtn.cloneNode(true);
editBtn.replaceWith(saveBtn);
saveBtn.addEventListener('click', (e) => { e.stopPropagation(); save(); });
```

---

#### Step 1-H: 復元時重複タブ防止（H-07 解決）

**作業内容:** background.js の `restoreAllGroups()` に既存タブURLセットとの差分チェックを追加する。

```javascript
// background.js
const existingTabs = await chrome.tabs.query({});
const existingUrls = new Set(existingTabs.map(t => t.url).filter(Boolean));

// 各グループの復元対象から既存URLを除外
const restorableTabs = group.tabs
  .filter(t => isRestorable(t.url))
  .filter(t => !existingUrls.has(t.url));
```

**完了条件:** Chrome起動後に同URLのタブが2つ以上開かないこと。手動復元ボタンを2回押してもタブが倍増しないこと。

---

#### Step 1-I: 重要操作の background.js 委譲（H-04 解決）

**作業内容:** 自動分類の「適用」処理のみ background.js に委譲する（最小限の対応）。

```javascript
// popup.js
async function handleApplyClassify() {
  const response = await chrome.runtime.sendMessage({
    type: MessageTypes.APPLY_CLASSIFICATION,
    proposals: AppState.classifyProposals,
  });
  if (response?.success) {
    closeModal(DOM.modalClassify());
    await renderAll();
    showToast(`${response.groupCount}グループを作成しました`, 'success');
  }
}

// background.js
if (message.type === MessageTypes.APPLY_CLASSIFICATION) {
  bulkCreateGroups(message.proposals)
    .then(count => sendResponse({ success: true, groupCount: count }))
    .catch(err => sendResponse({ success: false, error: err.message }));
  return true; // 非同期レスポンスのためtrueを返す
}
```

---

#### Step 1-J: 削除確認モーダル化（D-06 解決 ※ブロッカー扱い）

**作業内容:** `window.confirm()` を廃止し、popup.html に確認モーダルを追加する。

```html
<!-- popup.html に追加 -->
<div id="confirmModal" class="modal hidden">
  <div class="modal-content">
    <p id="confirmMessage"></p>
    <p id="confirmSubMessage" class="modal-sub"></p>
    <div class="modal-actions">
      <button id="confirmOkBtn" class="btn btn-danger">削除する</button>
      <button id="confirmCancelBtn" class="btn btn-ghost">キャンセル</button>
    </div>
  </div>
</div>
```

---

### フェーズ2: v1.0.0リリース後 推奨修正（v1.1.0）

| 項目 | 内容 | 想定時間 |
|---|---|---|
| H-02 | ストレージMutex実装（Race Condition対策） | 1時間 |
| H-08 | タブ上限のハードコード解消（設定値参照に変更） | 30分 |
| S-02 | updateGroupホワイトリスト化 | 30分 |
| D-02 | ストレージ容量超過検知・警告表示 | 1時間 |
| D-03 | データマイグレーション実装（将来のスキーマ変更に備え） | 1時間 |
| D-04 | 復元タブ全体上限のフロントエンド統合 | 30分 |
| D-05 | popup.css テーマ統一（ダーク/ライト選択） | 1〜2時間 |

### フェーズ3: v1.2.0以降 任意対応

| 項目 | 内容 |
|---|---|
| S-03 | faviconの外部リクエスト抑制（Base64保存またはChromeキャッシュAPI利用） |
| D-01 | 自動分類アルゴリズムの精度向上（バックエンドのカテゴリルール統合） |
| H-03 | ID生成の完全UUID化（`crypto.randomUUID()` への一本化 ※Chrome 92+対応済み） |

---

<a id="6"></a>
## 6. 今後の運用方針

### 6.1 バージョン管理方針

```
v1.0.0  ── フェーズ1修正完了後にリリース（Chrome拡張機能管理画面でロード開始）
v1.1.0  ── フェーズ2修正完了後（運用開始から2〜4週間後目安）
v1.2.0〜 ── 使用状況を見ながら任意追加
```

バージョン番号は `manifest.json` の `"version"` フィールドで管理する。Gitを使用する場合はタグ（`v1.0.0`）を付与すること。

### 6.2 データバックアップ方針

chrome.storage.local はブラウザのプロファイルデータに保存されるため、以下のリスクがある。

| リスク | 影響 | 対策 |
|---|---|---|
| ブラウザのデータ消去 | グループ情報の全損失 | v1.1 でJSONエクスポート機能を追加することを推奨 |
| OS再インストール | 同上 | 同上 |
| 拡張機能のアンインストール | 同上 | アンインストール前に手動エクスポートをユーザーに促すToast通知 |

**推奨:** v1.1 に「グループ設定をJSONでエクスポート/インポートする機能」を追加する。実装コストが小さく、データ保全のリスクを大幅に低減できる。

### 6.3 ストレージ監視方針

```javascript
// popup.js 起動時に容量チェックを実施
const usage = await checkStorageUsage();
if (usage.isCritical) {
  showToast('⚠️ ストレージが95%以上使用中です。グループを整理してください。', 'error', 10000);
} else if (usage.isWarning) {
  showToast('⚠️ ストレージが80%使用中です。', 'warning', 5000);
}
```

個人利用・100タブ以下の想定では5MBに達することは考えにくいが、念のため実装する。

### 6.4 Chrome APIの変更追従方針

| 確認タイミング | 確認内容 |
|---|---|
| Chromeの自動更新の通知を受けた時 | リリースノートで `tabs`, `storage`, Service Worker に関する変更を確認 |
| 拡張機能が突然動かなくなった時 | DevTools → Service Worker のエラーログを最初に確認 |
| 年1回程度 | [Chrome for Developers Blog](https://developer.chrome.com/blog) で Manifest V3 の更新状況を確認 |

### 6.5 既知の制限事項（v1.0.0時点）

以下は仕様上の制限として文書化し、ユーザー（= 自分）が認識した上で運用する。

| # | 制限事項 | 回避方法 |
|---|---|---|
| L-01 | Chromeがクラッシュ終了した場合、onStartupが発火せず自動復元されない | ポップアップの「手動復元」ボタンを使用する |
| L-02 | 復元時、グループのタブを一括で開くため、多グループかつ多タブ時にブラウザが重くなる | `maxRestoreTabsPerGroup=20`・`maxRestoreTabsTotal=50` の上限設定で軽減 |
| L-03 | デバイス間同期は非対応 | v1.0 の仕様外。必要になった場合は別途設計する |
| L-04 | `chrome://`, `chrome-extension://` 等の内部ページはグループに追加できない | 仕様として許容（保存しても復元できないURLは意味がないため正しい挙動） |
| L-05 | ポップアップで処理中にポップアップ外をクリックすると、グループ作成・タブ追加処理が中断される可能性がある（H-04はv1.0で自動分類適用のみ対応） | 操作中はポップアップ外をクリックしない |

---

<a id="7"></a>
## 7. 承認状況と次のアクション

### 7.1 最終承認状況

| 役割 | 確認状況 | コメント |
|---|---|---|
| マネージャー | ✅ **承認済み** | フェーズ1修正完了を条件にv1.0.0リリースを承認 |
| エンジニア | ⏳ **対応中** | フェーズ1: Step 1-A〜1-J の実施が必要 |
| QA | ✅ **検証完了** | 修正後に受け入れ条件の再テストを実施すること |

### 7.2 リリースまでのアクションリスト

```
[ ] Step 1-A: ES Modules統一（C-01・C-05）
[ ] Step 1-B: ストレージスキーマ統一（C-02）
[ ] Step 1-C: constants.js 作成・メッセージ統一（C-03）
[ ] Step 1-D: classifier.js 出力形式統一（C-04）
[ ] Step 1-E: isSafeUrl() 統一実装（S-01・H-05）
[ ] Step 1-F: インラインイベントハンドラ除去（S-04）
[ ] Step 1-G: UIバグ修正3点（H-01・H-06・H-09）
[ ] Step 1-H: 復元時重複タブ防止（H-07）
[ ] Step 1-I: 自動分類適用のbackground委譲（H-04）
[ ] Step 1-J: 削除確認モーダル化（D-06）

── 上記完了後 ──────────────────────────────────────────────
[ ] 受け入れ条件 AC-01〜AC-07 の動作確認（全項目手動テスト）
[ ] Chrome拡張機能管理画面でロードし、エラーがないことを確認
[ ] DevTools → Service Worker のログでonStartup発火を確認
[ ] manifest.json version を "1.0.0" に設定
[ ] v1.0.0 として使用開始
```

### 7.3 マネージャーからのコメント

> フロントエンド・バックエンドそれぞれの実装は、機能の網羅性・コードの品質ともに**個別に見れば十分な水準**にある。問題の本質は「2つの実装が独立して設計されており、統合時の取り決めが事前に定義されなかった」点にある。
>
> フェーズ1の修正は、新機能の追加ではなく「2つの実装を1つに統合する作業」であるため、ロジックの再設計は最小限で済む。Step 1-A（ESM統一）が完了すれば残りの修正は順調に進む見通し。
>
> **作業の取り掛かり順は必ず 1-A → 1-B → 1-C の順で実施すること。** この3ステップが他の全修正の土台になるため、途中で別のステップに入らないよう注意されたい。
>
> v1.0.0リリース後は、まず2週間程度実際に使ってみてから v1.1.0 の作業に入ることを推奨する。使ってみて初めてわかるUXの問題（タブの多さ・復元のタイミングなど）を次のバージョンに反映させる方が、設計の的中率が上がる。

---

*本レポートは「計画書」および「QA統合レポート」を統括マネージャーが統合・整理したものです。*
*修正完了後、受け入れ条件の再テスト結果をもって本文書の「完了」とします。*
