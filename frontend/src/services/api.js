/**
 * @file Client HTTP de l'API, ajoutant le jeton porteur a chaque requete.
 */

import { API_BASE_URL } from '@/config.js'
import { getToken } from './auth.js'

/**
 * @param {string} path Chemin relatif, ex. "/users/keys/me".
 * @param {object} [options] Options fetch supplementaires.
 * @returns {Promise<object>} Le corps JSON de la reponse.
 * @throws {Error} Si la reponse n'est pas un succes HTTP.
 */
async function request(path, options = {}) {
    const token = getToken()
    if (!token) throw new Error('Non authentifie.')

    const response = await fetch(API_BASE_URL + path, {
        ...options,
        headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${token}`,
            ...(options.headers || {}),
        },
    })

    const body = await response.json().catch(() => ({}))
    if (!response.ok) {
        throw new Error(body.detail || `Erreur HTTP ${response.status}`)
    }
    return body
}

/** @param {string} path @returns {Promise<object>} */
export function apiGet(path) {
    return request(path)
}

/** @param {string} path @param {object} data @returns {Promise<object>} */
export function apiPost(path, data) {
    return request(path, { method: 'POST', body: JSON.stringify(data) })
}