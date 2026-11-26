import { useEffect, useRef, useState } from "react"
import { Link } from "react-router-dom"

import { listCampaigns, type CampaignSummary } from "../api"
import { Banner } from "../form"
import { useI18n } from "../i18n/language"
import { presentError } from "../presentError"
import type { MessageKey } from "../i18n/catalog"

const PHASE_KEYS: Record<CampaignSummary["phase"], MessageKey> = {
  recruiting: "phaseRecruiting",
  placing: "phasePlacing",
  preparing: "phasePreparing",
  orders: "phaseOrders",
  battles: "phaseBattles",
  finished: "phaseFinished",
}

export function CampaignListPage() {
  const { t } = useI18n()
  const mounted = useRef(true)
  const [rows, setRows] = useState<CampaignSummary[] | null>(null)
  const [errors, setErrors] = useState<Record<string, string[]>>({})

  useEffect(() => {
    mounted.current = true
    let current = true
    listCampaigns()
      .then((found) => {
        if (current) {
          setRows(found)
        }
      })
      .catch((error: unknown) => {
        if (current) {
          setErrors(presentError(error, "campaignsLoadFailed"))
        }
      })
    return () => {
      current = false
      mounted.current = false
    }
  }, [])

  if (rows === null && Object.keys(errors).length === 0) {
    return <p className="quiet">{t("loadingCampaigns")}</p>
  }

  return (
    <section className="campaign-list">
      <header className="stage">
        <img className="stage-photo" src="/campaign-hall.jpg" alt="" />
        <div className="stage-copy">
          <div>
            <p className="mark">{t("campaignsNav")}</p>
            <h1>{t("yourCampaigns")}</h1>
            <p>{t("campaignsLead")}</p>
          </div>
          <Link className="button-link" to="/campanas/nueva">
            {t("newCampaign")}
          </Link>
        </div>
      </header>
      <Banner errors={errors} fields={["form", "session", "campaign", "origin", "csrf"]} />
      {rows && rows.length === 0 ? (
        <div className="empty-panel">
          <img className="empty-photo" src="/campaign-seal.jpg" alt="" />
          <p>{t("noCampaigns")}</p>
          <Link className="button-link" to="/campanas/nueva">
            {t("createFirstCampaign")}
          </Link>
        </div>
      ) : null}
      {rows && rows.length > 0 ? (
        <ul className="campaign-cards">
          {rows.map((row, index) => (
            <li key={row.id}>
              <Link className={`campaign-card crop-${index % 3}`} to={`/campanas/${row.id}`}>
                <img src="/campaign-hall.jpg" alt="" />
                <span className="campaign-card-body">
                  <span className="campaign-card-name">{row.name}</span>
                  <span className="campaign-card-meta">
                    {t(PHASE_KEYS[row.phase])} · {row.role}
                  </span>
                </span>
              </Link>
            </li>
          ))}
        </ul>
      ) : null}
    </section>
  )
}
