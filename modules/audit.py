import hashlib
import json
import logging
from sqlalchemy.orm import Session
from modules.db import LedgerEntry, engine

logger = logging.getLogger(__name__)

class LedgerAuditor:
    """
    Motor criptográfico para garantizar la inmutabilidad de la contabilidad (Audit Trail).
    Basado en los principios de cadena de bloques (Blockchain).
    """
    
    @staticmethod
    def _serialize_entry(entry_data: dict) -> str:
        """
        Serializa canónicamente un diccionario de datos contables para hashing.
        """
        # Excluimos id y el propio hash para generar la firma de los contenidos puros.
        # Ordenamos las llaves alfabéticamente para evitar errores de orden en JSON.
        canonical_dict = {
            'date': str(entry_data.get('date', '')),
            'transaction_id': str(entry_data.get('transaction_id', '')),
            'debit_account': str(entry_data.get('debit_account', '')),
            'credit_account': str(entry_data.get('credit_account', '')),
            'amount': float(entry_data.get('amount', 0.0)),
            'ticker': str(entry_data.get('ticker', '')),
            'previous_hash': str(entry_data.get('previous_hash', ''))
        }
        return json.dumps(canonical_dict, sort_keys=True)

    @classmethod
    def generate_hash(cls, entry_data: dict) -> str:
        """
        Genera el hash SHA-256 de una transacción contable.
        """
        serialized_string = cls._serialize_entry(entry_data)
        return hashlib.sha256(serialized_string.encode('utf-8')).hexdigest()

    @classmethod
    def verify_chain(cls) -> dict:
        """
        Verifica toda la cadena de bloques del libro mayor desde el Génesis hasta el estado actual.
        Retorna un reporte de integridad.
        """
        try:
            with Session(engine) as session:
                entries = session.query(LedgerEntry).order_by(LedgerEntry.id).all()
                
                if not entries:
                    return {"status": "OK", "message": "Cadena vacía.", "valid_entries": 0}
                
                expected_previous = "GENESIS"
                
                for i, entry in enumerate(entries):
                    # Ignorar los bloques legacy (anteriores a Capa 11) que no tienen hashes
                    if entry.entry_hash is None and entry.previous_hash is None:
                        continue
                        
                    # 1. Validar encadenamiento
                    if entry.previous_hash != expected_previous:
                        return {
                            "status": "CORRUPTED", 
                            "message": f"Fallo de encadenamiento en registro ID {entry.id}. Se esperaba {expected_previous} pero se encontró {entry.previous_hash}.",
                            "valid_entries": i
                        }
                    
                    # 2. Validar Hash de Integridad del Bloque
                    data_dict = {
                        'date': entry.date.strftime('%Y-%m-%d') if hasattr(entry.date, 'strftime') else str(entry.date),
                        'transaction_id': entry.transaction_id,
                        'debit_account': entry.debit_account,
                        'credit_account': entry.credit_account,
                        'amount': entry.amount,
                        'ticker': entry.ticker if entry.ticker else '',
                        'previous_hash': entry.previous_hash
                    }
                    calculated_hash = cls.generate_hash(data_dict)
                    
                    if calculated_hash != entry.entry_hash:
                        return {
                            "status": "CORRUPTED",
                            "message": f"Firma digital inválida en registro ID {entry.id}. Los datos fueron alterados post-inserción.",
                            "valid_entries": i
                        }
                        
                    # Preparamos para el siguiente bloque
                    expected_previous = entry.entry_hash
                    
                return {
                    "status": "OK", 
                    "message": "Cadena íntegra matemáticamente.", 
                    "valid_entries": len(entries)
                }
        except Exception as e:
            logger.error(f"Error verificando auditoría: {e}")
            return {"status": "ERROR", "message": str(e), "valid_entries": 0}
