# Obsidian論文管理 タグ付けガイドライン

## 基本原則

### 1. 統一性の確保
- **複数形を優先**: `large-language-models`, `electronic-health-records`, `adverse-drug-events`
- **ハイフン区切りを使用**: スペースではなく`-`でつなぐ
- **略語は併記**: `natural-language-processing` + `nlp`

### 2. 階層化の回避
- ❌ `ai/machine-learning`, `nlp/named-entity-recognition`  
- ✅ フラットな構造: `artificial-intelligence`, `machine-learning`, `named-entity-recognition`

## カテゴリ別ルール

### 技術・手法系タグ

#### AI・機械学習
```
✅ 推奨
- artificial-intelligence (+ ai)
- machine-learning (+ ml) 
- deep-learning
- large-language-models (+ llm)
- natural-language-processing (+ nlp)

❌ 避ける
- artificial-intelligence-ai
- machine-learning-ml
- large-language-model (単数形)
```

#### NLP技術
```
✅ 推奨
- named-entity-recognition (+ ner)
- information-extraction
- relation-extraction
- text-classification

❌ 避ける  
- name-entity-recognition (typo)
- named-entity-recognition-ner (冗長)
```

#### 学習手法
```
✅ 推奨
- supervised-learning
- few-shot
- zero-shot
- in-context-learning
- prompt-engineering

❌ 避ける
- unsupervised-learning → supervised-learning に統一
```

### 医学・医療系タグ

#### 医療データ
```
✅ 推奨
- electronic-health-records (+ ehr)
- clinical-notes
- unstructured-data
- patient-reported-outcomes

❌ 避ける
- electronic-health-record (単数形)
- structured-data → unstructured-data に統一
```

#### 薬事・安全性
```
✅ 推奨  
- adverse-drug-events (+ ade)
- pharmacovigilance
- drug-safety
- adverse-events

❌ 避ける
- adverse-drug-event (単数形)
- adverse-drug-event-ade (冗長)
```

#### 疾患・専門分野
```
✅ 推奨
- pediatric-oncology
- rare-cancers
- clinical-trials
- oncology

❌ 避ける
- paediatric-oncology (米国綴り優先)
- rare-cancer (単数形)
- clinical-trial (単数形)
```

### 出版・年代系タグ

#### 年代
```
✅ 推奨
- year-2024
- year-2023
- year-2025

形式: year-YYYY (4桁年)
```

#### ジャーナル
```
✅ 推奨
- journal-jmir-medical-informatics
- journal-artificial-intelligence-in-medicine
- journal-journal-of-biomedical-informatics

形式: journal-[雑誌名を短縮・ハイフン区切り]
```

## 実装ルール

### タグの配置
1. **YAMLフロントマター**: メインタグ（検索・分類用）
```yaml
tags: ["natural-language-processing", "nlp", "clinical-decision-support"]
```

2. **本文中ハッシュタグ**: 補完・関連タグ
```markdown
#large-language-models #prompt-engineering #healthcare
```

### 推奨タグ数
- **YAMLタグ**: 5-12個
- **ハッシュタグ**: 3-8個
- **総数**: 15個以下

### 品質チェック項目
- [ ] 複数形/単数形の統一
- [ ] 略語の併記
- [ ] typoの確認
- [ ] 冗長な表現の除去
- [ ] 既存タグとの重複確認

## 具体例

### 良い例
```yaml
title: "Large Language Models in Clinical NLP"
tags: ["large-language-models", "llm", "natural-language-processing", "nlp", 
       "clinical-decision-support", "electronic-health-records", "ehr",
       "prompt-engineering", "evaluation", "year-2024"]
```

```markdown
#large-language-models #clinical-nlp #healthcare #prompt-engineering
```

### 悪い例（修正前）
```yaml
tags: ["large-language-model", "LLM", "natural-language-processing-nlp",
       "electronic-health-record", "clinical-decision-support-systems-cdss"]
```

## 統一済みタグマッピング

今回の統一作業で確定したマッピング:

| 旧タグ | 新タグ（推奨） |
|-------|---------------|
| `large-language-model` | `large-language-models` |
| `electronic-health-record` | `electronic-health-records` |
| `artificial-intelligence-ai` | `artificial-intelligence` |
| `natural-language-processing-nlp` | `natural-language-processing` |
| `adverse-drug-event` | `adverse-drug-events` |
| `named-entity-recognition-ner` | `named-entity-recognition` |
| `paediatric-oncology` | `pediatric-oncology` |
| `health-care` | `healthcare` |
| `neural-network` | `neural-networks` |
| `clinical-trial` | `clinical-trials` |

## 自動タグ付けの指針

### 必須タグ（論文なら必ず付ける）
1. **手法・技術**: 使用されている主要技術
2. **ドメイン**: 医療、臨床、バイオなど
3. **年代**: `year-YYYY`
4. **データ種別**: EHR、clinical notes等

### 推奨タグ
1. **評価手法**: evaluation, validation等
2. **ジャーナル**: 掲載誌
3. **略語**: 主要技術の略語併記

この指針に従って、今後のタグ付けを統一的に行うことで、検索性と整合性が向上します。