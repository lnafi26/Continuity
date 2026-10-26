// Browser-safe Supabase config, committed for the Cloudflare deployment.
window.SUPABASE_CONFIG = {
  url: "https://sufspyrtfameukkqxiuk.supabase.co",
  publishableKey: "sb_publishable_qLD4l3fXys8wcPXeA7aLgA_n9Q_6-4Q",
  // Base URL of the local Stage 0 OAuth server (backend/auth/server.py),
  // exposed via a Cloudflare Tunnel so the deployed site can reach it.
  // Quick-tunnel URLs are ephemeral -- this must be updated (and redeployed)
  // every time `cloudflared tunnel --url http://localhost:8765` restarts,
  // unless/until it's swapped for a named/persistent tunnel.
  oauthBaseUrl: "http://localhost:8766",
};
