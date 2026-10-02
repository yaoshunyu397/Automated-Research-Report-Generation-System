import type { AuthUser, CurrentPage, SelectionSetResponse } from '../types'

type NavbarProps = {
  currentPage: CurrentPage
  authUser: AuthUser
  selectResp: SelectionSetResponse | null
  onPageChange: (page: CurrentPage) => void
  onLogout: () => void
}

export function Navbar({ currentPage, authUser, selectResp, onPageChange, onLogout }: NavbarProps) {
  return (
    <nav className="navbar">
      <div className="navBrand">arXiv 调研报告生成系统</div>
      <div className="navTabs">
        <button className={`navTab ${currentPage === 'search' ? 'active' : ''}`} onClick={() => onPageChange('search')}>
          论文检索
        </button>
        <button className={`navTab ${currentPage === 'selection' ? 'active' : ''}`} onClick={() => onPageChange('selection')}>
          参考文献选择集
        </button>
        <button className={`navTab ${currentPage === 'report' ? 'active' : ''}`} onClick={() => onPageChange('report')}>
          报告生成
        </button>
      </div>
      {selectResp && currentPage === 'search' && (
        <button className="btn primary" onClick={() => onPageChange('report')}>进入报告生成 →</button>
      )}
      <div className="navUser">
        <span>当前用户：<b>{authUser.username}</b></span>
        <button className="btn" onClick={onLogout}>退出登录</button>
      </div>
    </nav>
  )
}
