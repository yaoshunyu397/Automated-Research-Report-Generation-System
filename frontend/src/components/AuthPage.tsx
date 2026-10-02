type AuthPageProps = {
  authMode: 'login' | 'register'
  authUsername: string
  authPassword: string
  authLoading: boolean
  authError: string | null
  onAuthModeChange: (mode: 'login' | 'register') => void
  onUsernameChange: (value: string) => void
  onPasswordChange: (value: string) => void
  onSubmit: () => void
}

export function AuthPage({
  authMode,
  authUsername,
  authPassword,
  authLoading,
  authError,
  onAuthModeChange,
  onUsernameChange,
  onPasswordChange,
  onSubmit,
}: AuthPageProps) {
  return (
    <div className="authShell">
      <div className="authHero">
        <div className="authBrandMark">S</div>
        <div>
          <div className="authKicker">Survey Research Assistant</div>
          <h1>调研报告生成系统</h1>
          <p>登录后保存你的检索结果、论文解析任务和调研报告。不同用户的数据相互隔离，互不干扰。</p>
        </div>
        <div className="authFeatureList">
          <span>多用户选择集隔离</span>
          <span>论文下载与全文翻译</span>
          <span>报告在线生成与导出</span>
        </div>
      </div>
      <div className="authCard">
        <div className="authCardHead">
          <h2>{authMode === 'login' ? '欢迎回来' : '创建账号'}</h2>
          <p>{authMode === 'login' ? '请登录以继续使用系统' : '注册后即可开始保存个人选择集'}</p>
        </div>
        <div className="authTabs">
          <button className={authMode === 'login' ? 'authTab active' : 'authTab'} onClick={() => onAuthModeChange('login')}>登录</button>
          <button className={authMode === 'register' ? 'authTab active' : 'authTab'} onClick={() => onAuthModeChange('register')}>注册</button>
        </div>
        <div className="authForm">
          <label className="authField">
            <span>用户名</span>
            <input className="input authInput" value={authUsername} onChange={(e) => onUsernameChange(e.target.value)} placeholder="请输入用户名" name="survey2-login-username" autoComplete="off" spellCheck={false} />
          </label>
          <label className="authField">
            <span>密码</span>
            <input className="input authInput" type="password" value={authPassword} onChange={(e) => onPasswordChange(e.target.value)} placeholder="请输入至少 6 位密码" name="survey2-login-password" autoComplete="new-password" onKeyDown={(e) => e.key === 'Enter' && onSubmit()} />
          </label>
          {authError && <div className="authError">{authError}</div>}
          <button className="btn primary authSubmit" onClick={onSubmit} disabled={authLoading || !authUsername.trim() || authPassword.length < 6}>
            {authLoading ? '处理中...' : authMode === 'login' ? '登录' : '注册并登录'}
          </button>
          <div className="authSwitch">
            {authMode === 'login' ? '还没有账号？' : '已经有账号？'}
            <button onClick={() => onAuthModeChange(authMode === 'login' ? 'register' : 'login')}>
              {authMode === 'login' ? '立即注册' : '返回登录'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
