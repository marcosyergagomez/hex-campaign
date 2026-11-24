import { useEffect, useState, type FormEvent } from "react"

import { ApiError, currentPlayer, login, logout, type Player } from "../api"
import { Banner, Field } from "../form"

export function LoginPage() {
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [player, setPlayer] = useState<Player | null>(null)
  const [ready, setReady] = useState(false)
  const [pending, setPending] = useState(false)
  const [errors, setErrors] = useState<Record<string, string[]>>({})

  useEffect(() => {
    let alive = true
    currentPlayer()
      .then((found) => {
        if (alive) {
          setPlayer(found)
        }
      })
      .catch((error: unknown) => {
        if (alive) {
          setErrors(
            error instanceof ApiError
              ? error.errors
              : { form: ["No se ha podido comprobar la sesión."] },
          )
        }
      })
      .finally(() => {
        if (alive) {
          setReady(true)
        }
      })
    return () => {
      alive = false
    }
  }, [])

  async function onSubmit(event: FormEvent) {
    event.preventDefault()
    setPending(true)
    setErrors({})
    try {
      setPlayer(await login(email, password))
    } catch (error) {
      setErrors(error instanceof ApiError ? error.errors : { form: ["No se ha podido entrar."] })
    } finally {
      setPending(false)
    }
  }

  async function onLogout() {
    setPending(true)
    setErrors({})
    try {
      await logout()
      setPlayer(null)
      setPassword("")
    } catch (error) {
      setErrors(
        error instanceof ApiError ? error.errors : { form: ["No se ha podido cerrar la sesión."] },
      )
    } finally {
      setPending(false)
    }
  }

  if (!ready) {
    return <p className="quiet">Comprobando la sesión…</p>
  }

  if (player) {
    return (
      <div className="session">
        <h2>Sesión abierta</h2>
        <p>
          Has entrado como <strong>{player.alias}</strong>.
        </p>
        <p className="quiet">{player.email}</p>
        <Banner errors={errors} fields={["form", "origin", "csrf", "session"]} />
        <button type="button" onClick={onLogout} disabled={pending}>
          {pending ? "Cerrando…" : "Cerrar sesión"}
        </button>
      </div>
    )
  }

  return (
    <form onSubmit={onSubmit} noValidate>
      <Banner errors={errors} fields={["form", "credentials", "origin"]} />
      <Field
        label="Correo"
        name="email"
        type="email"
        autoComplete="username"
        value={email}
        error={errors.email}
        onChange={setEmail}
      />
      <Field
        label="Contraseña"
        name="password"
        type="password"
        autoComplete="current-password"
        value={password}
        error={errors.password}
        onChange={setPassword}
      />
      <button type="submit" disabled={pending}>
        {pending ? "Entrando…" : "Entrar"}
      </button>
    </form>
  )
}
