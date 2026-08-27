import { createClient } from "https://esm.sh/@supabase/supabase-js@2";
import {
  createDailExternalIngressHandler,
  type IngestRpcArguments,
} from "./handler.ts";

const handler = createDailExternalIngressHandler({
  getEnv: (name) => Deno.env.get(name),
  createRpcClient: (url, serviceRoleKey) => {
    const client = createClient(url, serviceRoleKey, {
      auth: {
        autoRefreshToken: false,
        detectSessionInUrl: false,
        persistSession: false,
      },
    });
    return {
      rpc: async (name: string, args: IngestRpcArguments) => {
        const { data, error } = await client.rpc(name, args);
        return { data, error };
      },
    };
  },
});

Deno.serve(handler);
