"""
Obsidian連携サービス
論文データをObsidian用のMarkdown形式でエクスポート
"""

import os
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any
from urllib.parse import quote

from ..config import config
from ..models.paper import PaperMetadata
from ..utils.logger import get_logger

logger = get_logger(__name__)

# タグ正規化マッピング（tagging_guidelines.mdに基づく）
TAG_NORMALIZATION_MAP = {
    # 単数形→複数形
    "large-language-model": "large-language-models",
    "electronic-health-record": "electronic-health-records", 
    "adverse-drug-event": "adverse-drug-events",
    "neural-network": "neural-networks",
    "clinical-trial": "clinical-trials",
    "rare-cancer": "rare-cancers",
    
    # 冗長表現→簡潔表現
    "artificial-intelligence-ai": "artificial-intelligence",
    "machine-learning-ml": "machine-learning",
    "natural-language-processing-nlp": "natural-language-processing",
    "named-entity-recognition-ner": "named-entity-recognition",
    "adverse-drug-event-ade": "adverse-drug-events",
    "clinical-decision-support-systems-cdss": "clinical-decision-support",
    
    # 表記統一
    "paediatric-oncology": "pediatric-oncology",
    "health-care": "healthcare",
    "name-entity-recognition": "named-entity-recognition",
    "structured-data": "unstructured-data",
    "unsupervised-learning": "supervised-learning",
    
    # 短縮形マッピング（略語を正規形に）
    "llm": "large-language-models",
    "nlp": "natural-language-processing", 
    "ehr": "electronic-health-records",
    "ade": "adverse-drug-events",
    "ner": "named-entity-recognition",
    "ai": "artificial-intelligence",
    "ml": "machine-learning"
}

# 必須併記タグ（メインタグに対応する略語を自動追加）
REQUIRED_ABBREVIATIONS = {
    "large-language-models": "llm",
    "natural-language-processing": "nlp",
    "electronic-health-records": "ehr", 
    "adverse-drug-events": "ade",
    "named-entity-recognition": "ner",
    "artificial-intelligence": "ai",
    "machine-learning": "ml"
}


class ObsidianExportService:
    """Obsidian Vault エクスポートサービス"""
    
    def __init__(self):
        self.vault_path = Path(config.obsidian.vault_path)
        self.enabled = config.obsidian.enabled
        
        if self.enabled:
            self._ensure_vault_structure()
    
    def _ensure_vault_structure(self):
        """Obsidian Vaultの基本構造を作成"""
        try:
            # 基本フォルダ作成
            self.vault_path.mkdir(parents=True, exist_ok=True)
            
            if config.obsidian.organize_by_year:
                papers_dir = self.vault_path / "papers"
                papers_dir.mkdir(exist_ok=True)
            
            if config.obsidian.include_pdf_attachments:
                attachments_dir = self.vault_path / "attachments" / "pdfs"
                attachments_dir.mkdir(parents=True, exist_ok=True)
            
            # テンプレートディレクトリ
            templates_dir = self.vault_path / "templates"
            templates_dir.mkdir(exist_ok=True)
            
            # 基本テンプレートファイル作成
            template_file = templates_dir / "paper_template.md"
            if not template_file.exists():
                self._create_paper_template(template_file)
            
            logger.info(f"Obsidian Vault構造を作成: {self.vault_path}")
            
        except Exception as e:
            logger.error(f"Obsidian Vault構造作成エラー: {e}")
    
    def _create_paper_template(self, template_path: Path):
        """基本的な論文テンプレートを作成"""
        template_content = """---
title: "{{title}}"
authors: {{authors}}
journal: "{{journal}}"
year: {{year}}
doi: "{{doi}}"
pmid: "{{pmid}}"
pubmed_url: "{{pubmed_url}}"
tags: {{tags}}
notion_id: "{{notion_id}}"
created: {{created}}
processed: {{processed}}
---

# {{title}}

## 📖 基本情報

- **著者**: {{authors_text}}
- **雑誌**: {{journal}}
- **発行年**: {{year}}
- **DOI**: [{{doi}}]({{doi_url}})
- **PMID**: [{{pmid}}]({{pubmed_url}})

## 🔬 要約

{{summary}}

## 🏷️ キーワード

{{keywords_tags}}

## 📎 関連ファイル

{{attachments}}

## 🔗 関連情報

- [Notion記事]({{notion_url}})
"""
        
        try:
            with open(template_path, 'w', encoding='utf-8') as f:
                f.write(template_content)
        except Exception as e:
            logger.warning(f"テンプレートファイル作成エラー: {e}")
    
    def _find_existing_file_by_pmid(self, pmid: str) -> Optional[Path]:
        """PMIDで既存ファイルを検索"""
        if not pmid:
            return None

        try:
            papers_dir = self.vault_path / "papers"
            if not papers_dir.exists():
                return None

            # 全Markdownファイルを検索
            for md_file in papers_dir.rglob("*.md"):
                try:
                    with open(md_file, 'r', encoding='utf-8') as f:
                        content = f.read(1000)  # 最初の1000文字のみ読む（効率化）

                        # YAMLフロントマターからpmidを抽出
                        if f'pmid: "{pmid}"' in content:
                            return md_file
                except Exception as e:
                    logger.warning(f"ファイル読み込みエラー [{md_file}]: {e}")
                    continue

            return None

        except Exception as e:
            logger.error(f"既存ファイル検索エラー（PMID）: {e}")
            return None

    def _find_existing_file_by_doi(self, doi: str) -> Optional[Path]:
        """DOIで既存ファイルを検索"""
        if not doi:
            return None

        try:
            papers_dir = self.vault_path / "papers"
            if not papers_dir.exists():
                return None

            # DOIの正規化（大文字小文字、プレフィックスの有無に対応）
            normalized_doi = doi.lower().replace('https://doi.org/', '').replace('http://doi.org/', '')

            # 全Markdownファイルを検索
            for md_file in papers_dir.rglob("*.md"):
                try:
                    with open(md_file, 'r', encoding='utf-8') as f:
                        content = f.read(1000)  # 最初の1000文字のみ読む（効率化）

                        # YAMLフロントマターからdoiを抽出して正規化
                        if 'doi: "' in content:
                            # doi: "xxx" の部分を抽出
                            import re
                            match = re.search(r'doi: "([^"]+)"', content)
                            if match:
                                file_doi = match.group(1).lower().replace('https://doi.org/', '').replace('http://doi.org/', '')
                                if file_doi == normalized_doi:
                                    return md_file
                except Exception as e:
                    logger.warning(f"ファイル読み込みエラー [{md_file}]: {e}")
                    continue

            return None

        except Exception as e:
            logger.error(f"既存ファイル検索エラー（DOI）: {e}")
            return None

    def _resolve_filename_conflict(self, base_path: Path, filename: str) -> Path:
        """ファイル名の衝突を解決（連番追加）"""
        file_path = base_path / f"{filename}.md"

        if not file_path.exists():
            return file_path

        # ファイルが存在する場合、連番を追加
        counter = 2
        while True:
            new_filename = f"{filename}_{counter}"
            file_path = base_path / f"{new_filename}.md"
            if not file_path.exists():
                logger.info(f"ファイル名衝突回避: {filename}.md -> {new_filename}.md")
                return file_path
            counter += 1

            # 無限ループ防止
            if counter > 100:
                raise Exception(f"ファイル名衝突解決失敗: {filename}")

    async def export_paper(self, paper: PaperMetadata, pdf_path: Optional[str] = None,
                          notion_page_id: Optional[str] = None) -> bool:
        """論文をObsidian Vaultにエクスポート"""
        if not self.enabled:
            return True

        try:
            logger.info(f"Obsidian エクスポート開始: {paper.title[:50]}...")

            # 重複チェック: PMID → DOI の順で確認
            # 1. PMIDで重複チェック
            if paper.pmid:
                existing_file = self._find_existing_file_by_pmid(paper.pmid)
                if existing_file:
                    logger.info(f"既存ファイル発見（PMID: {paper.pmid}）: {existing_file}")
                    logger.info(f"既にエクスポート済みのためスキップします")
                    return True

            # 2. DOIで重複チェック（PMIDがないか、PMIDで見つからなかった場合）
            if paper.doi:
                existing_file = self._find_existing_file_by_doi(paper.doi)
                if existing_file:
                    logger.info(f"既存ファイル発見（DOI: {paper.doi}）: {existing_file}")
                    logger.info(f"既にエクスポート済みのためスキップします")
                    return True

            # Markdownファイル生成
            markdown_content = self._create_markdown(paper, notion_page_id)

            # ファイル名生成
            filename = self._generate_filename(paper)

            # 保存先決定
            if config.obsidian.organize_by_year and paper.year:
                year_dir = self.vault_path / "papers" / str(paper.year)
                year_dir.mkdir(parents=True, exist_ok=True)
                file_path = self._resolve_filename_conflict(year_dir, filename)
            else:
                papers_dir = self.vault_path / "papers"
                papers_dir.mkdir(exist_ok=True)
                file_path = self._resolve_filename_conflict(papers_dir, filename)

            # Markdownファイル保存
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(markdown_content)

            # PDFファイルコピー（オプション）
            if config.obsidian.include_pdf_attachments and pdf_path:
                await self._copy_pdf_attachment(pdf_path, filename)

            logger.info(f"Obsidian エクスポート完了: {file_path}")
            return True

        except Exception as e:
            logger.error(f"Obsidian エクスポートエラー: {e}")
            return False
    
    def _create_markdown(self, paper: PaperMetadata, notion_page_id: Optional[str] = None) -> str:
        """Markdown形式の論文ファイルを生成"""
        try:
            # メタデータ準備
            authors_list = [f'"{author}"' for author in paper.authors] if paper.authors else []
            authors_yaml = "[" + ", ".join(authors_list) + "]"
            authors_text = ", ".join(paper.authors) if paper.authors else "不明"
            
            # タグ生成
            tags = self._generate_tags(paper)
            tags_yaml = "[" + ", ".join([f'"{tag}"' for tag in tags]) + "]"
            keywords_tags = " ".join([f"#{tag}" for tag in tags]) if tags else ""
            
            # URL生成
            doi_url = f"https://doi.org/{paper.doi}" if paper.doi else ""
            pubmed_url = f"https://pubmed.ncbi.nlm.nih.gov/{paper.pmid}/" if paper.pmid else ""
            notion_url = f"https://www.notion.so/{notion_page_id.replace('-', '')}" if notion_page_id else ""
            
            # 添付ファイルリンク
            attachments = self._generate_attachment_links(paper)
            
            # 日時
            now = datetime.now()
            created = now.isoformat()
            processed = now.isoformat()
            
            # Frontmatter
            frontmatter = f"""---
title: "{paper.title}"
authors: {authors_yaml}
journal: "{paper.journal or ''}"
year: {paper.year or 'null'}
doi: "{paper.doi or ''}"
pmid: "{paper.pmid or ''}"
pubmed_url: "{pubmed_url}"
tags: {tags_yaml}
notion_id: "{notion_page_id or ''}"
created: {created}
processed: {processed}
---"""
            
            # 本文
            content = f"""
# {paper.title}

## 📖 基本情報

- **著者**: {authors_text}
- **雑誌**: {paper.journal or '不明'}
- **発行年**: {paper.year or '不明'}"""
            
            if paper.doi:
                content += f"\n- **DOI**: [{paper.doi}]({doi_url})"
            
            if paper.pmid:
                content += f"\n- **PMID**: [{paper.pmid}]({pubmed_url})"
            
            content += f"""

## 🔬 要約

{paper.summary or '要約が利用できません。'}"""
            
            if keywords_tags:
                content += f"""

## 🏷️ キーワード

{keywords_tags}"""
            
            # 添付ファイル欄は内容がある場合のみ表示
            if attachments:
                content += f"""

## 📎 関連ファイル

{attachments}"""
            
            if notion_url:
                content += f"""

## 🔗 関連情報

- [Notion記事]({notion_url})"""
            
            return frontmatter + content
            
        except Exception as e:
            logger.error(f"Markdown生成エラー: {e}")
            return self._create_fallback_markdown(paper, notion_page_id)
    
    def _create_fallback_markdown(self, paper: PaperMetadata, notion_page_id: Optional[str] = None) -> str:
        """エラー時のフォールバックMarkdown"""
        return f"""---
title: "{paper.title or 'Unknown Title'}"
created: {datetime.now().isoformat()}
error: true
---

# {paper.title or 'Unknown Title'}

**エラーが発生しました。基本情報のみ表示しています。**

- **著者**: {', '.join(paper.authors) if paper.authors else '不明'}
- **雑誌**: {paper.journal or '不明'}
- **年**: {paper.year or '不明'}

## 要約

{paper.summary or 'エラーにより要約を表示できません。'}
"""
    
    def _generate_tags(self, paper: PaperMetadata) -> List[str]:
        """Obsidianタグを生成（tagging_guidelines.mdに準拠）"""
        tags = []
        
        # 1. 論文のキーワードを最優先でタグ化（内容ベース）
        if config.obsidian.tag_keywords and paper.keywords:
            for keyword in paper.keywords:
                # タグ形式に変換
                tag = self._sanitize_tag(keyword)
                if tag and len(tag) >= 3:
                    # ガイドラインに基づくタグ正規化
                    normalized_tag = self._normalize_tag(tag)
                    if normalized_tag not in tags:
                        tags.append(normalized_tag)
                    
                    # 必須略語の自動追加
                    if normalized_tag in REQUIRED_ABBREVIATIONS:
                        abbrev = REQUIRED_ABBREVIATIONS[normalized_tag]
                        if abbrev not in tags:
                            tags.append(abbrev)
        
        # 2. 年をタグに追加（重要な分類軸）
        if paper.year:
            year_tag = f"year-{paper.year}"
            if year_tag not in tags:
                tags.append(year_tag)
        
        # 3. 雑誌名は最後に追加（オプション的、タグが少ない場合のみ）
        if paper.journal and len(tags) < 10:
            journal_tag = self._sanitize_tag(paper.journal)
            if journal_tag:
                journal_tag = f"journal-{journal_tag}"
                if journal_tag not in tags:
                    tags.append(journal_tag)
        
        return tags[:15]  # ガイドライン上限15個
    
    def _sanitize_tag(self, text: str) -> str:
        """テキストをObsidianタグ形式に変換"""
        if not text:
            return ""
        
        # 小文字に変換し、特殊文字を除去
        tag = text.lower()
        tag = re.sub(r'[^a-z0-9\s-]', '', tag)
        tag = re.sub(r'\s+', '-', tag.strip())
        tag = re.sub(r'-+', '-', tag)
        tag = tag.strip('-')
        
        return tag if len(tag) >= 2 else ""
    
    def _normalize_tag(self, tag: str) -> str:
        """ガイドラインに基づくタグ正規化"""
        if not tag:
            return ""
        
        # 正規化マッピングを適用
        normalized = TAG_NORMALIZATION_MAP.get(tag, tag)
        
        # ガイドライン追加ルール（複数形優先、但し例外あり）
        if not normalized.endswith('s') and not normalized.startswith(('year-', 'journal-')):
            # 複数形化しない例外
            exceptions = {
                'artificial-intelligence', 'machine-learning', 'deep-learning', 
                'natural-language-processing', 'data', 'analysis', 'research', 
                'learning', 'processing', 'mining', 'healthcare', 'evaluation',
                'validation', 'prompt-engineering', 'in-context-learning'
            }
            
            if normalized not in exceptions:
                # 一般的な複数形化
                if normalized.endswith('y') and len(normalized) > 3 and normalized[-2] not in 'aeiou':
                    # technology -> technologies
                    normalized = normalized[:-1] + 'ies'
                elif normalized.endswith(('s', 'x', 'z', 'ch', 'sh')):
                    normalized += 'es'
                elif normalized.endswith('f'):
                    normalized = normalized[:-1] + 'ves'
                elif normalized.endswith('fe'):
                    normalized = normalized[:-2] + 'ves'
                elif not normalized.endswith(('ing', 'tion', 'sion', 'ness', 'ment', 'ship')):
                    normalized += 's'
        
        return normalized
    
    def _generate_filename(self, paper: PaperMetadata) -> str:
        """ファイル名を生成"""
        try:
            # 最初の著者を取得
            first_author = ""
            if paper.authors:
                first_author = paper.authors[0].split(',')[0].strip()
                first_author = re.sub(r'[^\w\s-]', '', first_author)
                first_author = re.sub(r'\s+', '_', first_author)
            
            # タイトルを短縮
            title_short = ""
            if paper.title:
                # 特殊文字を除去し、単語を取得
                words = re.findall(r'\w+', paper.title)
                title_short = '_'.join(words[:5])  # 最初の5単語
            
            # 年
            year = str(paper.year) if paper.year else "Unknown"
            
            # フォーマット適用
            if config.obsidian.filename_format == "{first_author}_{year}_{title_short}":
                filename = f"{first_author}_{year}_{title_short}"
            else:
                filename = f"{first_author}_{year}_{title_short}"
            
            # ファイル名サイズ制限
            if len(filename) > config.obsidian.max_filename_length:
                filename = filename[:config.obsidian.max_filename_length]
            
            # 空やすべてアンダースコアの場合のフォールバック
            if not filename or filename.replace('_', '').strip() == '':
                filename = f"paper_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            return filename
            
        except Exception as e:
            logger.warning(f"ファイル名生成エラー: {e}")
            return f"paper_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    def _generate_attachment_links(self, paper: PaperMetadata) -> str:
        """添付ファイルリンクを生成"""
        if not config.obsidian.include_pdf_attachments:
            return ""  # PDF保存無効時は空文字列を返す
        
        filename = self._generate_filename(paper)
        pdf_filename = f"{filename}.pdf"
        
        return f"- [[attachments/pdfs/{pdf_filename}|原文PDF]]"
    
    async def _copy_pdf_attachment(self, pdf_path: str, filename: str):
        """PDFファイルをattachmentsフォルダにコピー"""
        try:
            source_path = Path(pdf_path)
            if not source_path.exists():
                logger.warning(f"PDFファイルが見つかりません: {pdf_path}")
                return
            
            attachments_dir = self.vault_path / "attachments" / "pdfs"
            attachments_dir.mkdir(parents=True, exist_ok=True)
            
            target_path = attachments_dir / f"{filename}.pdf"
            
            # ファイルコピー
            shutil.copy2(source_path, target_path)
            logger.info(f"PDFファイルをコピー: {target_path}")
            
        except Exception as e:
            logger.error(f"PDFファイルコピーエラー: {e}")
    
    def get_vault_status(self) -> Dict[str, Any]:
        """Vaultの状態を取得（GUI表示用）"""
        try:
            if not self.enabled:
                return {"enabled": False}
            
            vault_exists = self.vault_path.exists()
            
            stats = {
                "enabled": True,
                "vault_path": str(self.vault_path),
                "vault_exists": vault_exists,
                "total_papers": 0,
                "folders": []
            }
            
            if vault_exists:
                papers_dir = self.vault_path / "papers"
                if papers_dir.exists():
                    # 論文数カウント
                    md_files = list(papers_dir.rglob("*.md"))
                    stats["total_papers"] = len(md_files)
                    
                    # フォルダ情報
                    if config.obsidian.organize_by_year:
                        for year_dir in papers_dir.iterdir():
                            if year_dir.is_dir():
                                year_files = len(list(year_dir.glob("*.md")))
                                stats["folders"].append({
                                    "name": year_dir.name,
                                    "count": year_files
                                })
            
            return stats
            
        except Exception as e:
            logger.error(f"Vault状態取得エラー: {e}")
            return {"enabled": self.enabled, "error": str(e)}


# シングルトンインスタンス
obsidian_service = ObsidianExportService()