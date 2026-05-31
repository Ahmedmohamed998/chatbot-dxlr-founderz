import asyncio
import re
import os
import asyncpg

DB_URL = os.getenv("DATABASE_URL", "postgresql://whatsapp_user:whatsapp_pass@postgres:5432/whatsapp_db")

async def fix_names():
    pool = await asyncpg.create_pool(DB_URL)
    async with pool.acquire() as conn:
        contacts = await conn.fetch("SELECT id, name FROM contacts")
        updated_count = 0
        for contact in contacts:
            old_name = contact['name']
            if not old_name:
                continue
                
            # If name contains letters, let's extract ONLY the numbers and hyphens
            if not bool(re.match(r'^[\d\s\-]+$', old_name)):
                # Extract all digits from the string
                # E.g. "ربيع السيد - 8528" -> "8528"
                # "Customer - 123 - 456" -> "123 - 456"
                numbers = re.findall(r'\d+', old_name)
                if numbers:
                    new_name = " - ".join(numbers)
                    if new_name != old_name:
                        await conn.execute("UPDATE contacts SET name=$1 WHERE id=$2", new_name, contact['id'])
                        updated_count += 1
                        print(f"Updated '{old_name}' -> '{new_name}'")
        print(f"Successfully updated {updated_count} contacts!")

if __name__ == "__main__":
    asyncio.run(fix_names())
