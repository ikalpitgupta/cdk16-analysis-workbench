import { Component, type ErrorInfo, type ReactNode } from 'react'

interface Props { children: ReactNode }
interface State { error: Error | null }

/* App-level error boundary: keeps navigation alive when a page throws,
   and surfaces the failure in a readable, recoverable state. */
export default class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null }

  static getDerivedStateFromError(error: Error): State {
    return { error }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    // eslint-disable-next-line no-console
    console.error('Page error:', error.message, info.componentStack?.split('\n').slice(0, 4).join(' | '))
  }

  render() {
    if (this.state.error) {
      return (
        <div className="notice notice-coral" role="alert" style={{ margin: 24 }}>
          <strong>Something went wrong rendering this page.</strong>
          <div className="mono" style={{ fontSize: 12, marginTop: 8, wordBreak: 'break-word' }}>
            {this.state.error.message}
          </div>
          <button className="btn mt-2" onClick={() => this.setState({ error: null })}>Try again</button>
        </div>
      )
    }
    return this.props.children
  }
}
