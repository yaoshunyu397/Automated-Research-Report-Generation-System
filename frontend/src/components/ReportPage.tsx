import type { ReportOutlineTemplate, ReportSection, SelectionSetResponse } from '../types'

type ReportPageProps = {
  loading: boolean
  error: string | null
  reportProgressMessage: string | null
  selectResp: SelectionSetResponse | null
  reportCompletion: { total: number; filled: number; percent: number }
  parsedPaperCount: number
  outlineTemplates: ReportOutlineTemplate[]
  outlineRows: Array<{ sec: ReportSection; depth: number }>
  activeSection: ReportSection | null
  activeSectionId: number | null
  draftContent: string
  reportTitle: string
  onCreateReport: () => void
  onApplyOutlineTemplate: (template: ReportOutlineTemplate) => void
  onGenerateFullReport: () => void
  onExitSelectionSet: () => void
  onExportReport: (format: 'md' | 'docx' | 'pdf') => void
  onSetCurrentPage: (page: 'search' | 'selection' | 'report') => void
  onSelectSection: (sectionId: number, content: string) => void
  onGenerateSection: () => void
  onSaveContent: () => void
  onUpdateDraftContent: (value: string) => void
  onUpdateSectionTitle: (sectionId: number, title: string) => void
}

export function ReportPage({
  loading,
  error,
  reportProgressMessage,
  selectResp,
  reportCompletion,
  parsedPaperCount,
  outlineTemplates,
  outlineRows,
  activeSection,
  activeSectionId,
  draftContent,
  reportTitle,
  onCreateReport,
  onApplyOutlineTemplate,
  onGenerateFullReport,
  onExitSelectionSet,
  onExportReport,
  onSetCurrentPage,
  onSelectSection,
  onGenerateSection,
  onSaveContent,
  onUpdateDraftContent,
  onUpdateSectionTitle,
}: ReportPageProps) {
  return (
    <div className="page">
      <div className="panel">
        <div className="panelHead">
          <h2>{reportTitle}</h2>
          <div className="right">
            <span className="muted">选择集：{selectResp ? <><b>{selectResp.name}</b>（{selectResp.query || '未记录关键词'}）（{selectResp.count} 篇）</> : '未选择'}</span>
            <button className="btn" onClick={onCreateReport} disabled={loading || !selectResp || parsedPaperCount === 0} title={!selectResp ? '请先保存或加载选择集' : parsedPaperCount === 0 ? '请先在论文检索页完成正文解析' : undefined}>创建报告</button>
            <button className="btn primary" onClick={onGenerateFullReport} disabled={loading || !selectResp}>自动生成整篇报告</button>
            <button className="btn" onClick={onExitSelectionSet} disabled={loading}>退出该选择集</button>
            <button className="btn" onClick={() => onExportReport('md')} disabled={!selectResp || loading}>导出 MD</button>
            <button className="btn" onClick={() => onExportReport('docx')} disabled={!selectResp || loading}>导出 Word</button>
            <button className="btn" onClick={() => onExportReport('pdf')} disabled={!selectResp || loading}>导出 PDF</button>
          </div>
        </div>
        {error && <div className="error">{error}</div>}
        {reportProgressMessage && <div className="ok">{reportProgressMessage}</div>}
        {selectResp && parsedPaperCount === 0 && (
          <div className="error">当前选择集还没有完成正文解析的论文。请回到论文检索页执行“下载 PDF”和“解析正文”后，再创建报告。</div>
        )}
        {selectResp && parsedPaperCount > 0 && (
          <div className="ok">当前选择集中已有 {parsedPaperCount} 篇论文完成正文解析，可以创建报告。</div>
        )}
        {outlineTemplates.length > 0 && (
          <div className="templatePicker">
            <div className="templatePickerHead">
              <div>
                <div className="savedReportsTitle">请选择一种目录模板</div>
                <div className="muted">系统已基于当前选题推荐 3 种风格不同的调研报告目录。</div>
              </div>
            </div>
            <div className="templateGrid">
              {outlineTemplates.map((template) => (
                <button key={template.template_id} className="templateCard" onClick={() => onApplyOutlineTemplate(template)}>
                  <div className="templateCardTitle">{template.name}</div>
                  <div className="templateCardDesc">{template.description}</div>
                  <div className="templateCardFoot">点击应用此模板</div>
                </button>
              ))}
            </div>
          </div>
        )}

        {selectResp && (
          <div className="reportCompletionCard">
            <div className="reportCompletionTop">
              <span>报告章节完成度</span>
              <b>{reportCompletion.percent}%</b>
            </div>
            <div className="progressTrack"><div className="progressFill" style={{ width: `${reportCompletion.percent}%` }} /></div>
            <div className="muted">已完成 {reportCompletion.filled}/{reportCompletion.total} 个章节内容</div>
          </div>
        )}
        {!selectResp && (
          <div className="empty">请先在
            <button className="linkBtn" onClick={() => onSetCurrentPage('search')}>论文检索</button>
            页面搜索并保存选择集。
          </div>
        )}
        {outlineRows.length === 0 && selectResp && parsedPaperCount > 0 && <div className="empty">创建报告后请选择一个目录模板，然后即可自动生成整篇报告。</div>}
        {outlineRows.length > 0 && (
          <div className="editorGrid fullHeight">
            <div className="outlineList">
              {outlineRows.map(({ sec, depth }) => (
                <div key={sec.id}
                  className={`outlineRow ${sec.id === activeSectionId ? 'active' : ''}`}
                  style={{ paddingLeft: 10 + depth * 16 }}
                  onClick={() => onSelectSection(sec.id, sec.content_md ?? '')}
                  role="button" tabIndex={0}>
                  <span className="bullet">{depth === 0 ? '•' : '◦'}</span>
                  <input className="outlineInput" defaultValue={sec.title}
                    onClick={(e) => e.stopPropagation()}
                    onBlur={(e) => onUpdateSectionTitle(sec.id, e.target.value)} />
                </div>
              ))}
            </div>
            <div className="editorPane">
              <div className="editorHead">
                <div className="editorTitle">{activeSection ? `当前章节：${activeSection.title}` : '点击左侧章节进行编辑'}</div>
                <div className="right">
                  <button className="btn" onClick={onGenerateSection} disabled={loading || !activeSectionId}>生成本章内容</button>
                  <button className="btn primary" onClick={onSaveContent} disabled={loading || !activeSectionId}>保存</button>
                </div>
              </div>
              <textarea className="editorTextarea" value={draftContent}
                onChange={(e) => onUpdateDraftContent(e.target.value)}
                placeholder="选择左侧章节后，可手动编辑或点击'生成本章内容'。" />
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
