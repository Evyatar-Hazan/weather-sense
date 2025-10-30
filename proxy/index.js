/**
 * Cloudflare Worker Reverse Proxy for WeatherSense Health Check Endpoint
 * 
 * This Worker provides a zero-cost solution to the Google Cloud Run `/healthz` restriction.
 * It maps `/healthz` requests to the Cloud Run `/health` endpoint while preserving
 * all other functionality.
 * 
 * Functionality:
 * - /healthz → proxies to Cloud Run /health endpoint
 * - All other paths → forwards directly to Cloud Run service
 * 
 * Google Cloud Run Issue:
 * Cloud Run reserves paths ending with 'z' (including /healthz) and returns 404.
 * This proxy maintains assignment compliance by exposing /healthz externally
 * while using /health internally.
 */

// Cloud Run service configuration
// Replace this URL with your actual Cloud Run service URL
const CLOUD_RUN_BASE_URL = "https://weather-sense-service-ektuy7j2kq-uc.a.run.app";

// CORS headers for API compliance
const CORS_HEADERS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type, x-api-key, Accept",
  "Access-Control-Max-Age": "86400",
};

/**
 * Main Worker request handler
 * @param {Request} request - Incoming request object
 * @param {Object} env - Environment variables
 * @param {Object} ctx - Execution context
 * @returns {Response} - Proxied response
 */
export default {
  async fetch(request, env, ctx) {
    try {
      const url = new URL(request.url);
      const path = url.pathname;
      
      // Handle CORS preflight requests
      if (request.method === "OPTIONS") {
        return new Response(null, {
          status: 200,
          headers: CORS_HEADERS,
        });
      }
      
      // Special handling for /healthz endpoint
      if (path === "/healthz") {
        return await handleHealthzRequest(request);
      }
      
      // Forward all other requests to Cloud Run service
      return await forwardRequest(request, url);
      
    } catch (error) {
      console.error("Proxy error:", error.message);
      return new Response(
        JSON.stringify({
          error: "proxy_error",
          message: "Internal proxy error occurred"
        }),
        {
          status: 502,
          headers: {
            "Content-Type": "application/json",
            ...CORS_HEADERS,
          },
        }
      );
    }
  },
};

/**
 * Handle /healthz requests by proxying to /health endpoint
 * @param {Request} request - Original request object
 * @returns {Response} - Health check response
 */
async function handleHealthzRequest(request) {
  try {
    // Create new request to /health endpoint
    const healthUrl = `${CLOUD_RUN_BASE_URL}/health`;
    
    const healthRequest = new Request(healthUrl, {
      method: request.method,
      headers: request.headers,
      body: request.method !== "GET" && request.method !== "HEAD" 
        ? request.body 
        : null,
    });
    
    // Fetch from Cloud Run /health endpoint
    const response = await fetch(healthRequest);
    
    // Clone response to add CORS headers
    const modifiedResponse = new Response(response.body, {
      status: response.status,
      statusText: response.statusText,
      headers: {
        ...Object.fromEntries(response.headers),
        ...CORS_HEADERS,
      },
    });
    
    return modifiedResponse;
    
  } catch (error) {
    console.error("Health check proxy error:", error.message);
    
    // Return error response that matches API format
    return new Response(
      JSON.stringify({
        error: "health_check_unavailable",
        message: "Health check endpoint temporarily unavailable"
      }),
      {
        status: 502,
        headers: {
          "Content-Type": "application/json",
          ...CORS_HEADERS,
        },
      }
    );
  }
}

/**
 * Forward requests to Cloud Run service preserving all request details
 * @param {Request} request - Original request object
 * @param {URL} url - Parsed URL object
 * @returns {Response} - Forwarded response
 */
async function forwardRequest(request, url) {
  try {
    // Construct target URL with same path and query parameters
    const targetUrl = `${CLOUD_RUN_BASE_URL}${url.pathname}${url.search}`;
    
    // Create forwarded request with same headers and body
    const forwardedRequest = new Request(targetUrl, {
      method: request.method,
      headers: request.headers,
      body: request.method !== "GET" && request.method !== "HEAD" 
        ? request.body 
        : null,
    });
    
    // Fetch from Cloud Run service
    const response = await fetch(forwardedRequest);
    
    // Clone response to add CORS headers
    const modifiedResponse = new Response(response.body, {
      status: response.status,
      statusText: response.statusText,
      headers: {
        ...Object.fromEntries(response.headers),
        ...CORS_HEADERS,
      },
    });
    
    return modifiedResponse;
    
  } catch (error) {
    console.error("Forward request error:", error.message);
    
    // Return error response
    return new Response(
      JSON.stringify({
        error: "service_unavailable",
        message: "Backend service temporarily unavailable"
      }),
      {
        status: 502,
        headers: {
          "Content-Type": "application/json",
          ...CORS_HEADERS,
        },
      }
    );
  }
}