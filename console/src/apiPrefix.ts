/** Where core is reached from the browser: behind the dev proxy at /api, or on the page's own origin. */
export const API_PREFIX = import.meta.env.VITE_SAME_ORIGIN_API === 'true' ? '' : '/api'
