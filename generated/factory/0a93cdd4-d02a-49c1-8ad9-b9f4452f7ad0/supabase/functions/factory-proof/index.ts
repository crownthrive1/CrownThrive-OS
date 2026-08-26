import "jsr:@supabase/functions-js/edge-runtime.d.ts";
const SERVICE="crownthrive-factory-proof";
Deno.serve(async(req:Request)=>{const u=new URL(req.url);if(req.method==="GET"&&u.pathname.endsWith("/health"))return Response.json({ok:true,service:SERVICE,generated_by:"ct-factory-compiler.v3"});if(req.method!=="GET")return Response.json({error:"method_not_allowed"},{status:405});return Response.json({service:SERVICE,message:"Autonomous compiler/provider proof"});});

