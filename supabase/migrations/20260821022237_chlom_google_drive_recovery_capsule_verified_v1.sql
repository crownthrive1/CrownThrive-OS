update chlom_runtime.backup_manifests
set destination_ref='gdrive:file:1sBBtLc1m6k9MAeZ9ebQiX2Hbxfk751dX',
    content_sha256='e166f4265d7af9e306579a281abc9cba030f35836b2cd7753e04c980f5712c11',
    manifest_sha256=encode(extensions.digest(convert_to(
      backup_class || '|' || source_system || '|' || destination_system || '|' ||
      'gdrive:file:1sBBtLc1m6k9MAeZ9ebQiX2Hbxfk751dX' || '|' || encryption_profile || '|' ||
      'e166f4265d7af9e306579a281abc9cba030f35836b2cd7753e04c980f5712c11','UTF8'),'sha256'),'hex'),
    backup_state='verified',
    verified_at=now(),
    metadata=metadata || jsonb_build_object(
      'drive_folder_id','1FKmR4rHNvxG7Inof37mD1mTK06O-T-yV',
      'drive_file_id','1sBBtLc1m6k9MAeZ9ebQiX2Hbxfk751dX',
      'bytes',1714,
      'cipher','AES-256-GCM',
      'kdf','scrypt',
      'roundtrip_decryption_verified',true,
      'wrong_password_rejected',true,
      'drive_readback_checksum_verified',true,
      'secret_value_in_drive_metadata',false
    )
where backup_class='institutional-fallback-vault' and backup_state='planned';

update integration_control.credential_continuity_registry
set recovery_present=true,
    continuity_state='verified_dual_reference',
    recovery_note='Supabase Vault is primary. Google Drive contains a ciphertext-only CHLOM recovery capsule with independently verified byte-for-byte readback. Recovery password is not stored in Drive metadata or public documentation.',
    last_verified_at=now(),
    updated_at=now()
where credential_id='cred.chlom.fallback-vault-password';

select chlom_runtime.append_dail_event(
  'backup.recovery_capsule.verified','backup','chlom-fallback-vault-v1',
  jsonb_build_object(
    'destination','google_drive',
    'drive_file_id','1sBBtLc1m6k9MAeZ9ebQiX2Hbxfk751dX',
    'sha256','e166f4265d7af9e306579a281abc9cba030f35836b2cd7753e04c980f5712c11',
    'bytes',1714,
    'cipher','AES-256-GCM',
    'kdf','scrypt',
    'readback_verified',true,
    'password_exposed',false
  ),
  'founder-directive-2026-08-20',null,'ct.agent.founder-orchestrator','1',null,null,'D2 founder authorized recovery control',null,'restricted'
);