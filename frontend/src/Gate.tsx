import { NavLink, Outlet } from "react-router-dom"

export function Gate() {
  return (
    <main className="gate">
      <section className="gate-story">
        <p className="mark">Hex Campaign</p>
        <h1>La mesa está puesta</h1>
        <p>Mapa de campaña para miniaturas. Las órdenes se cierran aquí; la batalla se juega en la mesa.</p>
      </section>
      <section className="panel">
        <nav className="tabs" aria-label="Cuenta">
          <NavLink to="/entrar">Entrar</NavLink>
          <NavLink to="/alta">Crear cuenta</NavLink>
        </nav>
        <Outlet />
      </section>
    </main>
  )
}
