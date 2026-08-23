/**
 * @file Authentification OpenID Connect (Authorization Code + PKCE).
 *
 * Le jeton d'acces est conserve UNIQUEMENT en memoire, jamais dans
 * localStorage : il disparait a la fermeture de l'onglet et ne survit pas
 * a une session. Un jeton persiste serait lisible par tout script injecte
 * dans la page, et resterait exploitable longtemps apres le depart de
 * l'utilisateur.
 */

import { KEYCLOAK_REALM_URL, KEYCLOAK_CLIENT_ID } from '@/config.js'

const AUTH_URL = `${KEYCLOAK_REALM_URL}/protocol/openid-connect/auth`
const TOKEN_URL = `${KEYCLOAK_REALM_URL}/protocol/openid-connect/token`
const REDIRECT_URI = `${location.origin}/`

let accessToken = null

/** @param {ArrayBuffer|Uint8Array} buf @returns {string} base64url */
function b64url(buf) {
    return btoa(String.fromCharCode(...new Uint8Array(buf)))
        .replace(/\+/g, '-')
        .replace(/\//g, '_')
        .replace(/=+$/, '')
}

/**
 * Redirige vers Keycloak pour authentifier l'utilisateur.
 * @returns {Promise<void>} Ne rend jamais la main : la page est quittee.
 */
export async function login() {
    const verifier = b64url(crypto.getRandomValues(new Uint8Array(32)))
    sessionStorage.setItem('pkce_verifier', verifier)

    const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(verifier))

    const url = new URL(AUTH_URL)
    url.searchParams.set('client_id', KEYCLOAK_CLIENT_ID)
    url.searchParams.set('redirect_uri', REDIRECT_URI)
    url.searchParams.set('response_type', 'code')
    url.searchParams.set('scope', 'openid')
    url.searchParams.set('code_challenge', b64url(digest))
    url.searchParams.set('code_challenge_method', 'S256')

    location.href = url.toString()
}

/**
 * A appeler au chargement de l'application : si Keycloak a renvoye un code
 * d'autorisation, l'echange contre un jeton d'acces.
 * @returns {Promise<object|null>} Les revendications du jeton, ou null.
 */
export async function handleRedirect() {
    const code = new URLSearchParams(location.search).get('code')
    if (!code) return null

    history.replaceState({}, '', REDIRECT_URI)

    const response = await fetch(TOKEN_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: new URLSearchParams({
            grant_type: 'authorization_code',
            client_id: KEYCLOAK_CLIENT_ID,
            code,
            redirect_uri: REDIRECT_URI,
            code_verifier: sessionStorage.getItem('pkce_verifier'),
        }),
    })

    const data = await response.json()
    sessionStorage.removeItem('pkce_verifier')
    if (!data.access_token) throw new Error(data.error_description || 'Echec de l\'authentification.')

    accessToken = data.access_token
    const payload = accessToken.split('.')[1].replace(/-/g, '+').replace(/_/g, '/')
    return JSON.parse(atob(payload + '='.repeat((4 - (payload.length % 4)) % 4)))
}

/** @returns {string|null} Le jeton d'acces courant. */
export function getToken() {
    return accessToken
}

/** Oublie le jeton. */
export function logout() {
    accessToken = null
}