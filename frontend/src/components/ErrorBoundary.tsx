import { Component, type ReactNode } from "react"

import { useI18n } from "../i18n/language"

type BoundaryProps = { children: ReactNode }

type BoundaryState = { failed: boolean }

/**
 * React only reports a render failure through a class boundary.
 * The notice itself is a function component so it can follow the active language.
 */
export class ErrorBoundary extends Component<BoundaryProps, BoundaryState> {
  state: BoundaryState = { failed: false }

  static getDerivedStateFromError(): BoundaryState {
    return { failed: true }
  }

  private recover = () => {
    this.setState({ failed: false })
  }

  render() {
    if (this.state.failed) return <RenderFailed onRetry={this.recover} />
    return this.props.children
  }
}

function RenderFailed({ onRetry }: { onRetry: () => void }) {
  const { t } = useI18n()
  return (
    <section className="session" role="alert">
      <h1>{t("renderFailed")}</h1>
      <p>{t("renderFailedLead")}</p>
      <button type="button" onClick={onRetry}>{t("renderRetry")}</button>
    </section>
  )
}
