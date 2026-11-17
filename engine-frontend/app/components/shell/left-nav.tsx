import { useEffect } from "react";
import { Link, NavLink, useLocation } from "react-router";
import logo from "../../assets/logo-line-white.png";
import type { User } from "../../demo/types";
import { START_PATH, isAvailable, navGroups } from "../../lib/nav";
import { isLive } from "../../lib/data-mode";
import { lastUrlInSection, rememberUrl } from "../../lib/page-memory";

export function LeftNav({ user }: { user: User }) {
  const { pathname, search } = useLocation();
  useEffect(() => {
    rememberUrl(pathname, search);
  }, [pathname, search]);
  return (
    <nav className="left-nav" aria-label="Main">
      <div className="left-nav__brand">
        <div className="left-nav__lockup">
          <Link className="left-nav__logo-link" to={START_PATH} aria-label={isLive ? "Wusool Engine, go to Buyers" : "Wusool Engine, go to Home"}>
            <img className="left-nav__logo" src={logo} alt="" />
          </Link>
          <span className="left-nav__product">Engine</span>
        </div>
        {!isLive && <span className="badge left-nav__demo">Demo</span>}
      </div>

      {/* On phone only Home is offered, so it gets its own link outside the groups. */}
      <NavLink className="left-nav__phone-home" to={START_PATH} end>
        {isLive ? "Buyers" : "Home"}
      </NavLink>

      {/* Groups are shown by the hairline between them; a visible label read as one more link (8 Nov 2026). */}
      <div className="left-nav__groups">
        {navGroups.map((group) => (
          <div className="left-nav__group" key={group.label}>
            <ul className="left-nav__list" aria-label={group.label}>
              {group.items.map((item) => (
                <li key={item.path}>
                  {!isAvailable(item) ? (
                    <span className="left-nav__item left-nav__item--off" aria-disabled="true">
                      <item.icon size={16} aria-hidden="true" />
                      {item.label}
                    </span>
                  ) : item.external ? (
                    <a className="left-nav__item" href={item.path} target="_blank" rel="noreferrer">
                      <item.icon size={16} aria-hidden="true" />
                      {item.label}
                      <span className="visually-hidden"> (opens in a new tab)</span>
                    </a>
                  ) : (
                    <NavLink
                      className={({ isActive }) => (isActive || item.alsoActiveOn?.some((path) => pathname.startsWith(path)) ? "left-nav__item active" : "left-nav__item")}
                      to={lastUrlInSection(item.path)}
                      end={item.path === "/"}
                    >
                      <item.icon size={16} aria-hidden="true" />
                      {item.label}
                    </NavLink>
                  )}
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>

      <div className="left-nav__footer">
        {isLive ? (
          // The profile page is a placeholder with no backend yet, so live mode shows the name only.
          <span className="left-nav__profile left-nav__profile--off" aria-disabled="true">
            <span className="avatar" aria-hidden="true">{user.name.charAt(0)}</span>
            <span className="left-nav__profile-text">
              <span className="left-nav__profile-name">{user.name}</span>
              <span className="left-nav__profile-role">{user.title}</span>
            </span>
          </span>
        ) : (
          <NavLink className="left-nav__profile" to="/profile">
            <span className="avatar" aria-hidden="true">{user.name.charAt(0)}</span>
            <span className="left-nav__profile-text">
              <span className="left-nav__profile-name">{user.name}</span>
              <span className="left-nav__profile-role">{user.title}</span>
            </span>
          </NavLink>
        )}
      </div>
    </nav>
  );
}
