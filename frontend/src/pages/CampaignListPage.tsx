import { useEffect, useRef, useState } from "react"
import { Link } from "react-router-dom"

import { deleteCampaign, listCampaigns, type CampaignSummary } from "../api"
import { Banner } from "../form"
import { clientNotice, type MessageKey } from "../i18n/catalog"
import { useI18n } from "../i18n/language"
import { subscribeLive } from "../liveEvents"
import { presentError } from "../presentError"

const CARD_PHOTOS = ["/campaign-hall.jpg", "/campaign-seal.jpg", "/campaign-fortress.jpg"] as const

type Tab = "active" | "finished"

function statusKey(phase: CampaignSummary["phase"]): MessageKey {
  if (phase === "finished") return "statusFinished"
  if (phase === "orders" || phase === "battles") return "statusRunning"
  return "statusPrepared"
}

function isFinished(phase: CampaignSummary["phase"]): boolean {
  return phase === "finished"
}

function canLeave(row: CampaignSummary): boolean {
  return row.status === "active" && !isFinished(row.phase)
}

export function CampaignListPage() {
  const { t } = useI18n()
  const mounted = useRef(true)
  const [rows, setRows] = useState<CampaignSummary[] | null>(null)
  const [tab, setTab] = useState<Tab>("active")
  const [pendingId, setPendingId] = useState<string | null>(null)
  const [confirmRow, setConfirmRow] = useState<CampaignSummary | null>(null)
  const [typedName, setTypedName] = useState("")
  const [errors, setErrors] = useState<Record<string, string[]>>({})

  useEffect(() => {
    mounted.current = true
    let current = true

    async function load(quiet: boolean) {
      try {
        const found = await listCampaigns()
        if (current) {
          setRows(found)
          if (!quiet) setErrors({})
        }
      } catch (error: unknown) {
        if (current && !quiet) {
          setErrors(presentError(error, "campaignsLoadFailed"))
        }
      }
    }

    void load(false)
    const stop = subscribeLive((event) => {
      if (
        event.type === "campaigns" ||
        event.type === "campaign" ||
        event.type === "reconnect"
      ) {
        void load(true)
      }
    })
    return () => {
      current = false
      mounted.current = false
      stop()
    }
  }, [])

  function openConfirm(row: CampaignSummary) {
    if (!canLeave(row) || pendingId) {
      return
    }
    setErrors({})
    setTypedName("")
    setConfirmRow(row)
  }

  function closeConfirm() {
    if (pendingId) {
      return
    }
    setConfirmRow(null)
    setTypedName("")
  }

  async function onConfirmDelete() {
    if (!confirmRow || pendingId) {
      return
    }
    if (typedName.trim() !== confirmRow.name) {
      setErrors({ form: [clientNotice("scrapCampaignMismatch")] })
      return
    }
    const row = confirmRow
    setPendingId(row.id)
    setErrors({})
    try {
      await deleteCampaign(row.id, typedName.trim())
      if (!mounted.current) {
        return
      }
      setRows((current) => (current ? current.filter((item) => item.id !== row.id) : current))
      setConfirmRow(null)
      setTypedName("")
    } catch (error) {
      if (mounted.current) {
        setErrors(presentError(error, "deleteCampaignFailed"))
      }
    } finally {
      if (mounted.current) {
        setPendingId(null)
      }
    }
  }

  if (rows === null && Object.keys(errors).length === 0) {
    return <p className="quiet">{t("loadingCampaigns")}</p>
  }

  const active = rows?.filter((row) => !isFinished(row.phase)) ?? []
  const finished = rows?.filter((row) => isFinished(row.phase)) ?? []
  const shown = tab === "active" ? active : finished
  const emptyAll = Boolean(rows && rows.length === 0)

  return (
    <section className="campaign-list">
      <Banner errors={errors} />
      {emptyAll ? (
        <header className="stage stage-hero">
          <img className="stage-photo" src="/campaign-hall.jpg" alt="" />
          <div className="stage-copy">
            <div>
              <p className="mark">{t("campaignsNav")}</p>
              <h1>{t("yourCampaigns")}</h1>
              <p>{t("noCampaigns")}</p>
            </div>
            <Link className="button-link" to="/campanas/nueva">
              {t("createFirstCampaign")}
            </Link>
          </div>
        </header>
      ) : null}
      {rows && rows.length > 0 ? (
        <>
          <header className="campaigns-head">
            <div>
              <p className="mark">{t("campaignsNav")}</p>
              <h1>{t("yourCampaigns")}</h1>
              <p className="quiet">{t("campaignsLead")}</p>
            </div>
            <Link className="button-link" to="/campanas/nueva">
              {t("newCampaign")}
            </Link>
          </header>
          <div className="campaign-tabs" role="tablist" aria-label={t("campaignsNav")}>
            <button
              type="button"
              role="tab"
              aria-selected={tab === "active"}
              className={tab === "active" ? "is-active" : undefined}
              onClick={() => setTab("active")}
            >
              {t("campaignsActiveTab")}
              <span className="campaign-tab-count">{active.length}</span>
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={tab === "finished"}
              className={tab === "finished" ? "is-active" : undefined}
              onClick={() => setTab("finished")}
            >
              {t("campaignsFinishedTab")}
              <span className="campaign-tab-count">{finished.length}</span>
            </button>
          </div>
          {shown.length === 0 ? (
            <p className="quiet">
              {tab === "active" ? t("noActiveCampaigns") : t("noFinishedCampaigns")}
            </p>
          ) : (
            <ul className="campaign-cards">
              {shown.map((row, index) => (
                <li key={row.id} className="campaign-card-row">
                  <Link className={`campaign-card crop-${index % 3}`} to={`/campanas/${row.id}`}>
                    <img src={CARD_PHOTOS[index % CARD_PHOTOS.length]} alt="" />
                    <span className="campaign-card-body">
                      <span className="campaign-card-name">{row.name}</span>
                      <span className="campaign-card-meta">
                        {t(statusKey(row.phase))} · {row.role}
                      </span>
                    </span>
                  </Link>
                  {canLeave(row) ? (
                    <button
                      type="button"
                      className="button-quiet campaign-delete"
                      disabled={pendingId === row.id}
                      onClick={() => openConfirm(row)}
                    >
                      {pendingId === row.id ? t("deletingCampaign") : t("deleteCampaign")}
                    </button>
                  ) : null}
                </li>
              ))}
            </ul>
          )}
        </>
      ) : null}
      {confirmRow ? (
        <div className="scrap-modal" role="dialog" aria-modal="true" aria-labelledby="scrap-title">
          <div className="scrap-modal-panel">
            <h2 id="scrap-title">{t("scrapCampaignTitle")}</h2>
            <p>{t("scrapCampaignPrompt", { name: confirmRow.name })}</p>
            <label className="field">
              <span className="label-text">{t("campaignName")}</span>
              <input
                autoFocus
                value={typedName}
                onChange={(event) => setTypedName(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter") {
                    event.preventDefault()
                    void onConfirmDelete()
                  }
                  if (event.key === "Escape") {
                    event.preventDefault()
                    closeConfirm()
                  }
                }}
                disabled={pendingId === confirmRow.id}
                autoComplete="off"
                spellCheck={false}
              />
            </label>
            <div className="scrap-modal-actions">
              <button type="button" className="button-quiet" disabled={Boolean(pendingId)} onClick={closeConfirm}>
                {t("scrapCampaignCancel")}
              </button>
              <button
                type="button"
                disabled={pendingId === confirmRow.id || typedName.trim().length === 0}
                onClick={() => {
                  void onConfirmDelete()
                }}
              >
                {pendingId === confirmRow.id ? t("deletingCampaign") : t("deleteCampaign")}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </section>
  )
}
